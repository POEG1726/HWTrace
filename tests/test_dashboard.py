import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen
import json
import dashboard
import receiver


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(receiver.SCHEMA)
        self.db.execute(
            "INSERT INTO sensors VALUES ('s',1,0,2,'group','temperature','°C',1)"
        )
        for seq in range(1, 22, 2):
            self.db.execute(
                "INSERT INTO records VALUES ('s',?,?,'sample')",
                (seq, f"2026-01-01T00:00:{seq:02}Z"),
            )
            self.db.execute("INSERT INTO samples VALUES ('s',?,1,0,2,?)", (seq, seq))

    def tearDown(self):
        self.db.close()

    def test_sampling_uses_sample_ordinal_and_keeps_last(self):
        points = dashboard.series(self.db, "s", ["1:0:2"], max_points=5)[0]["points"]
        self.assertEqual([v for _, v in points], [1, 7, 13, 19, 21])

    def test_sessions_and_sensor_identity(self):
        self.assertEqual(dashboard.sessions(self.db)[0]["session"], "s")
        self.assertEqual(dashboard.sensors(self.db, "s")[0]["unit"], "°C")
        self.assertEqual(
            dashboard.series(self.db, "missing", ["1:0:2"])[0]["points"], []
        )

    def test_average_actual_samples_and_partial_group(self):
        points = dashboard.series(self.db, "s", ["1:0:2"], average=4)[0]["points"]
        self.assertEqual([p[1:] for p in points], [[4.0, 4], [12.0, 4], [19.0, 3]])
        self.assertEqual(points[0][0], "2026-01-01T00:00:07Z")

    def test_zoom_requeries_samples_in_time_range(self):
        from datetime import datetime, timezone

        ms = lambda second: int(
            datetime(2026, 1, 1, 0, 0, second, tzinfo=timezone.utc).timestamp() * 1000
        )
        points = dashboard.series(
            self.db, "s", ["1:0:2"], average=2, start=ms(5), end=ms(15)
        )[0]["points"]
        self.assertEqual([p[1:] for p in points], [[6.0, 2], [10.0, 2], [14.0, 2]])

    def test_extrema_include_points_omitted_by_downsampling(self):
        self.db.execute("UPDATE samples SET value=100 WHERE session='s' AND seq=3")
        result = dashboard.series(self.db, "s", ["1:0:2"], max_points=2)[0]
        self.assertEqual((result["min"], result["max"]), (1.0, 100.0))
        averaged = dashboard.series(self.db, "s", ["1:0:2"], max_points=2, average=2)[0]
        self.assertEqual((averaged["min"], averaged["max"]), (6.0, 50.5))

    def test_bad_average_and_range(self):
        with self.assertRaises(ValueError):
            dashboard.series(self.db, "s", ["1:0:2"], average=0)
        with self.assertRaises(ValueError):
            dashboard.series(self.db, "s", ["1:0:2"], start=100, end=10)

    def test_invalid_sensor_rejected(self):
        with self.assertRaises(ValueError):
            dashboard.series(self.db, "s", ["1:2"])


class DashboardHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fixture.sqlite3"
        db = sqlite3.connect(self.path)
        db.executescript(receiver.SCHEMA)
        db.execute(
            "INSERT INTO records VALUES ('synthetic',1,'2026-01-01T00:00:00Z','sample')"
        )
        db.commit()
        db.close()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), dashboard.handler(self.path)
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.temp.cleanup()

    def test_static_files_and_api_close_connections(self):
        for path, mime in [
            ("/", "text/html"),
            ("/app.js", "text/javascript"),
            ("/style.css", "text/css"),
        ]:
            with urlopen(self.url + path) as response:
                self.assertEqual(response.headers.get_content_type(), mime)
                self.assertTrue(response.read())
        connections = []
        real_connect = dashboard.connect

        def track(path):
            connection = real_connect(path)
            connections.append(connection)
            return connection

        with patch.object(dashboard, "connect", side_effect=track):
            with urlopen(self.url + "/api/sessions") as response:
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertEqual(json.load(response)[0]["session"], "synthetic")
        self.assertEqual(len(connections), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connections[0].execute("SELECT 1")

    def test_invalid_requests_and_read_only_database(self):
        for path, status in [
            ("/api/series?sensor=invalid", 400),
            ("/api/unknown", 404),
            ("/../receiver.py", 404),
        ]:
            with self.assertRaises(HTTPError) as error:
                urlopen(self.url + path)
            self.assertEqual(error.exception.code, status)
            error.exception.close()
        db = dashboard.connect(self.path)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                db.execute("DELETE FROM records")
            self.assertEqual(
                db.execute("SELECT count(*) FROM records").fetchone()[0], 1
            )
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
