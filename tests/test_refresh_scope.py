import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.refresh_scope import should_refresh


class RefreshScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Scope test')
        self.git('config', 'user.email', 'scope@example.invalid')
        self.before = self.commit('update.py', 'original')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True).strip()

    def commit(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        self.git('add', name)
        self.git('commit', '-qm', 'Test change')
        return self.git('rev-parse', 'HEAD')

    def test_source_change_before_final_documentation_commit_is_detected(self):
        self.commit('update.py', 'fixed')
        self.commit('README.md', 'Documentation')
        self.assertEqual(self.git('diff', '--name-only', 'HEAD^', 'HEAD'), 'README.md')
        self.assertTrue(should_refresh('push', self.before, root=self.root))

    def test_ui_and_docs_only_do_not_refresh_sources(self):
        self.commit('src/app.js', 'UI change')
        self.commit('README.md', 'Documentation')
        self.assertFalse(should_refresh('push', self.before, root=self.root))

    def test_seed_eligibility_change_refreshes_archive(self):
        self.commit('data/seed.json', '{"exclusions": ["corrected"]}')
        self.assertTrue(should_refresh('push', self.before, root=self.root))

    def test_queued_work_uses_all_changes_in_current_checkout(self):
        self.commit('reader_gateway.py', 'Source change')
        self.commit('data/archive.json', 'Newer published data')
        self.commit('README.md', 'Newer documentation')
        self.assertTrue(should_refresh('push', self.before, root=self.root))

    def test_unknown_push_base_requests_refresh(self):
        self.assertTrue(should_refresh('push', '0' * 40, root=self.root))

    def test_scheduled_and_manual_runs_always_refresh(self):
        for event in ('schedule', 'workflow_dispatch'):
            self.assertTrue(should_refresh(event, self.before, root=self.root))


if __name__ == '__main__':
    unittest.main()
