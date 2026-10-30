import base64
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import receiver

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhuQAAAAASUVORK5CYII=')

class StartupCaptureTests(unittest.TestCase):
    def test_upload_preserves_binary_and_records_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'capture.sqlite3'
            capture = 'a' * 32
            path = receiver.store_screenshot(db, capture, '2026-10-30T04:00:00Z', 'TEST-PC', 'TM5.exe', io.BytesIO(PNG), capture_tick_ms=1000, capture_finished_tick_ms=1015, capture_finished_at='2026-10-30T04:00:00.015Z')
            self.assertEqual(path.read_bytes(), PNG)
            conn = sqlite3.connect(db)
            try:
                row = conn.execute('select source_host,process_name,sha256,bytes from startup_captures').fetchone()
                self.assertEqual(row, ('TEST-PC','TM5.exe', hashlib.sha256(PNG).hexdigest(),len(PNG)))
                self.assertEqual(conn.execute('select started_uptime_ms,finished_uptime_ms from startup_capture_timing').fetchone(),(1000,1015))
            finally: conn.close()
            receiver.store_screenshot(db,capture,'2026-10-30T04:00:00Z','TEST-PC','TM5.exe',io.BytesIO(PNG))
            with self.assertRaises(ValueError):
                receiver.store_screenshot(db,'../escape','time','pc','TM5.exe',io.BytesIO(PNG))
    def test_invalid_image_does_not_create_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'capture.sqlite3'
            with self.assertRaises(ValueError):
                receiver.store_screenshot(db,'b'*32,'time','pc','TM5.exe',io.BytesIO(b'not a png'))
            self.assertFalse((Path(temp)/'screenshots').exists())
    def test_binary_cli_ack(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable,'receiver.py','--db',str(Path(temp)/'capture.sqlite3'),
                '--startup-screenshot','c'*32,'--captured-at','2026-10-30T04:00:00Z','--source-host','PC',
                '--process-name-b64',base64.b64encode(b'TM5.exe').decode()],input=PNG,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,b'STORED '+b'c'*32+b'\n')
    def test_image_and_telemetry_can_initialize_same_database_concurrently(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'concurrent.sqlite3'
            identity = dict(sensor_id=1,sensor_instance=0,reading_id=2)
            base = dict(version=1,session='concurrent',timestamp='2026-10-30T04:00:00Z')
            rows = [dict(base,seq=0,kind='metadata',sensors=[dict(identity,sensor_name='DIMM',reading_name='Temperature',reading_type=1,unit='C')]),
                    dict(base,seq=1,kind='sample',values=[dict(identity,value=42)],elapsed_ms=0,uptime_ms=1000)]
            common = [sys.executable,'receiver.py','--db',str(db)]
            image = common + ['--startup-screenshot','d'*32,'--captured-at','2026-10-30T04:00:00Z',
                '--source-host','PC','--process-name-b64',base64.b64encode(b'TM5.exe').decode()]
            with ThreadPoolExecutor(max_workers=2) as workers:
                a = workers.submit(subprocess.run,common+['--ack'],input=('\n'.join(json.dumps(x) for x in rows)+'\n').encode(),capture_output=True)
                b = workers.submit(subprocess.run,image,input=PNG,capture_output=True)
                for result in (a.result(),b.result()): self.assertEqual(result.returncode,0,result.stderr)
            conn=sqlite3.connect(db)
            try:
                self.assertEqual(conn.execute('select count(*) from samples').fetchone()[0],1)
                self.assertEqual(conn.execute('select count(*) from startup_captures').fetchone()[0],1)
            finally:conn.close()

    def test_elapsed_time_and_legacy_record_compatibility(self):
        conn=sqlite3.connect(':memory:');conn.executescript(receiver.SCHEMA)
        try:
            base=dict(version=1,session='timing',seq=0,timestamp='2026-10-30T04:00:00Z',kind='event',event='collector_start')
            receiver.ingest(conn,base)
            receiver.ingest(conn,dict(base,seq=1,elapsed_ms=500,uptime_ms=12345))
            self.assertEqual(conn.execute('select elapsed_ms from record_timing').fetchall(),[(500,)])
            self.assertEqual(conn.execute('select uptime_ms from record_uptime').fetchall(),[(12345,)])
            with self.assertRaises(ValueError): receiver.ingest(conn,dict(base,seq=2,elapsed_ms=-1))
            self.assertEqual(conn.execute('select count(*) from records').fetchone()[0],2)
        finally: conn.close()

if __name__=='__main__':unittest.main()
