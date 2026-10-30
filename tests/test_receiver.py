import copy
import sqlite3
import unittest
import receiver

class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript(receiver.SCHEMA)
        self.base = {'version': 1, 'session': 's', 'seq': 1, 'timestamp': '2026-01-01T00:00:00Z'}
        self.sensor = {'sensor_id': 1, 'sensor_instance': 2, 'reading_id': 3,
                       'sensor_name': 'DIMM', 'reading_name': 'Temperature',
                       'reading_type': 1, 'unit': '°C'}
    def test_ingest_and_duplicate(self):
        meta = dict(self.base, kind='metadata', sensors=[self.sensor])
        self.assertTrue(receiver.ingest(self.db, meta))
        self.assertFalse(receiver.ingest(self.db, meta))
        v = dict(self.sensor, value=42.5)
        receiver.ingest(self.db, dict(self.base, seq=2, kind='sample', values=[v]))
        receiver.ingest(self.db, dict(self.base, seq=3, kind='event', event='process_start', detail='TM5.exe'))
        self.assertEqual(self.db.execute('select value from samples').fetchone(), (42.5,))
        self.assertEqual(self.db.execute('select unit from sensors').fetchone(), ('°C',))
        self.assertEqual(self.db.execute('select count(*) from events').fetchone(), (1,))
    def test_transaction_rolls_back(self):
        with self.assertRaises(KeyError):
            receiver.ingest(self.db, dict(self.base, kind='metadata', sensors=[self.sensor, {}]))
        self.assertEqual(self.db.execute('select count(*) from records').fetchone(), (0,))
        self.assertEqual(self.db.execute('select count(*) from sensors').fetchone(), (0,))
    def test_missing_metadata_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            receiver.ingest(self.db, dict(self.base, kind='sample', values=[dict(self.sensor, value=1)]))
        self.assertEqual(self.db.execute('select count(*) from records').fetchone(), (0,))

if __name__ == '__main__':
    unittest.main()

