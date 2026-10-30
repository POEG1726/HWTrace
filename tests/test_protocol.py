import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class ProtocolTests(unittest.TestCase):
    def test_commit_ack_and_wal(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'test.db'
            row = {'version':1, 'session':'test', 'seq':0,
                   'timestamp':'2026-01-01T00:00:00Z', 'kind':'event',
                   'event':'marker', 'detail':'hello'}
            p = subprocess.run([sys.executable, 'receiver.py', '--db', str(db), '--ack'],
                               input=(json.dumps(row)+'\n')*2, text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout, 'OK\nOK\n')
            import sqlite3
            with __import__("contextlib").closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute('select count(*) from events').fetchone()[0],1)
                self.assertEqual(conn.execute('pragma journal_mode').fetchone()[0], 'wal')
    def test_bad_record_has_no_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run([sys.executable,'receiver.py','--db', str(Path(tmp)/'test.db'), '--ack'],
                               input='{"version":1}\n', text=True, capture_output=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual(p.stdout, '')

if __name__ == '__main__': unittest.main()
