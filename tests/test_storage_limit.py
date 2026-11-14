"""Startup quota cleanup with isolated caches, never real user files."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import storage
from core.service import Service
from tests.test_resources import ASSETS


class StorageLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'state'
        self.service = Service(ASSETS, self.root);self.addCleanup(self.service.shutdown)
        self.service.config['export_dir'] = str(self.root/'previews/exports')

    def file(self, name, size=10, age=100):
        path = self.root/name;path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'x'*size)
        os.utime(path, (age, age));os.utime(path.parent, (age, age))
        return path

    def test_limits_default_persist_validate_and_start_only_next_launch(self):
        self.assertEqual(self.service.state()['storage_limit_gb'], 0)
        self.assertFalse(self.service.state()['storage_limit_help_hidden'])
        with patch('core.service.threading.Timer') as timer:
            for value in storage.LIMITS_GB:
                self.service.settings({'storage_limit_gb': value})
            timer.assert_not_called()
            for bad in (True, False, '5', 5.0, None, -1, 2):
                with self.assertRaises(ValueError):self.service.settings({'storage_limit_gb':bad})
            self.service.settings({'storage_limit_gb':5})
            self.service.settings({'storage_limit_help_hidden':True})
            restarted = Service(ASSETS, self.root)
            self.assertEqual(restarted.state()['storage_limit_gb'],5)
            self.assertTrue(restarted.state()['storage_limit_help_hidden'])
            self.assertEqual(timer.call_args.args[0],10)
            timer.return_value.start.assert_called_once()
            restarted.shutdown()
            timer.return_value.cancel.assert_called_once()
        self.assertEqual(json.loads((self.root/'config.json').read_text('utf-8'))['storage_limit_gb'],5)

    def test_oldest_items_removed_until_cap_live_keys_and_exports_preserved(self):
        oldest = self.file('previews/old/result.bin',age=10)
        old = self.file('archives/account/snapshot_000000000000/old.db',age=20)
        newer = self.file('media-cache/account/downloads/new.media',age=30)
        avatar = self.file('avatar-cache/new.png',age=40)
        live = self.file('archives/account/snapshot_111111111111/live.db',age=1)
        keys = self.file('media-cache/account/image-keys.json',age=1)
        database_keys = self.file('archives/account/keys.json',age=1)
        exported = self.file('previews/exports/important.html',age=1)
        self.service.library = self.service.config['library'] = {'root':str(live.parent)}
        total = storage.storage_info(self.service)['bytes']
        job = self.service._new_job('storage_cleanup','Synthetic cap')
        storage.cleanup(self.service,job,limit_bytes=total-20)
        self.assertFalse(oldest.exists());self.assertFalse(old.exists())
        for path in (newer,avatar,live,keys,database_keys,exported):self.assertTrue(path.is_file(),str(path))
        self.assertEqual(job['freed_bytes'],20)
        self.assertEqual(storage.storage_info(self.service)['bytes'],total-20)

    def test_over_cap_preserves_live_data_even_when_limit_cannot_be_met(self):
        live = self.file('archives/account/snapshot_111111111111/live.db',size=100)
        self.service.library = self.service.config['library'] = {'root':str(live.parent)}
        job = self.service._new_job('storage_cleanup','Synthetic protected data')
        storage.cleanup(self.service,job,limit_bytes=1)
        self.assertTrue(live.is_file());self.assertEqual(job['freed_bytes'],0)
        self.assertIn('未强制删除',job['detail'])

    def test_busy_startup_defers_then_submits_once_and_below_cap_has_no_task(self):
        self.service._startup_storage_limit = self.service.config['storage_limit_gb'] = 1
        self.service._cache_readers = 1
        with patch.object(self.service,'_schedule_storage_check') as schedule,patch.object(self.service.pool,'submit') as submit:
            self.service._queue_storage_check()
            schedule.assert_called_once_with(5);submit.assert_not_called()
        self.service._cache_readers = 0
        with patch.object(self.service.pool,'submit') as submit:
            self.service._queue_storage_check()
        self.assertTrue(self.service._maintenance)
        submit.call_args.args[0]()
        self.assertFalse(self.service._maintenance);self.assertEqual(self.service.config['tasks'],[])

    def test_startup_over_cap_reuses_cleanup_task_and_shutdown_blocks_late_callback(self):
        self.service._startup_storage_limit = self.service.config['storage_limit_gb'] = 1
        old = self.file('previews/old/result.bin')
        total = 1024**3 + 10
        with patch.object(self.service.pool,'submit') as submit:
            self.service._queue_storage_check()
        with patch('core.storage.storage_info',return_value={'bytes':total}):
            submit.call_args.args[0]()
        job = self.service.config['tasks'][0]
        self.assertEqual(job['status'],'completed',job['detail'])
        self.assertEqual(job['freed_bytes'],10);self.assertFalse(old.exists())
        self.assertFalse(self.service._maintenance)
        self.service.shutdown()
        with patch.object(self.service.pool,'submit') as submit:
            self.service._queue_storage_check();submit.assert_not_called()

    def test_setting_save_failure_rolls_back(self):
        with patch.object(self.service,'save',side_effect=OSError('Synthetic disk error')):
            with self.assertRaises(OSError):self.service.settings({'storage_limit_gb':3})
        self.assertEqual(self.service.config['storage_limit_gb'],0)


if __name__ == '__main__':
    unittest.main()
