import json
import os
from pathlib import Path
import sqlite3
import subprocess
import unittest

import receiver


@unittest.skipUnless(
    os.name == "nt" and Path("build/test_native_snapshot.exe").exists(),
    "Build the Windows native fixtures to run this check",
)
class NativeOutputTests(unittest.TestCase):
    def test_initially_nonfinite_reading_keeps_metadata_for_later_sample(self):
        result = subprocess.run(
            ["build/test_native_snapshot.exe"], capture_output=True, check=True
        )
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        db = sqlite3.connect(":memory:")
        db.executescript(receiver.SCHEMA)
        try:
            for row in rows:
                receiver.ingest(db, row)
            self.assertEqual(len(rows[0]["sensors"]), 1)
            self.assertEqual(rows[1]["values"], [])
            self.assertEqual(
                db.execute("select value from samples").fetchone(), (42.5,)
            )
            self.assertEqual(
                db.execute("select unit from sensors").fetchone(), ("\u00b0C",)
            )
            self.assertEqual(
                db.execute("select count(*) from record_timing").fetchone()[0], 3
            )
            self.assertEqual(
                db.execute("select count(*) from record_uptime").fetchone()[0], 3
            )
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
