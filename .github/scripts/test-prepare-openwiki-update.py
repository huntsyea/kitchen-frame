"""Exercise publication decisions in disposable Git repositories, without inference."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('prepare-openwiki-update.sh').resolve()


class PrepareUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        for path, content in {
            'openwiki/.last-update.json': '{"status":"complete","gitHead":"previous"}\n',
            'openwiki/quickstart.md': '# Original\n',
            'AGENTS.md': 'Original instructions\n',
            '.github/workflows/openwiki-update.yml': 'original workflow\n',
        }.items():
            self.write(path, content)
        self.git('add', '.')
        self.git('commit', '-qm', 'Baseline')
        self.baseline = self.read('openwiki/.last-update.json')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def read(self, path):
        return (self.root / path).read_text()

    def prepare(self, outcome):
        self.write('openwiki/.last-update.json', '{"status":"' + ('complete' if outcome == 'success' else 'interrupted') + '","gitHead":"new"}\n')
        self.write('openwiki/.run.json', '{}\n')
        output = self.root / 'outputs'
        subprocess.run(['bash', str(SCRIPT), outcome], cwd=self.root,
                       env={**os.environ, 'GITHUB_OUTPUT': str(output)}, check=True,
                       capture_output=True, text=True)
        self.assertFalse((self.root / 'openwiki/.run.json').exists())
        return dict(line.split('=', 1) for line in output.read_text().splitlines())

    def test_failure_status_only(self):
        self.assertEqual(self.prepare('failure')['has-pages'], 'false')
        self.assertEqual(self.read('openwiki/.last-update.json'), self.baseline)
        self.assertEqual(self.git('diff', '--cached'), '')

    def test_success_status_only(self):
        self.assertEqual(self.prepare('success')['has-pages'], 'false')
        self.assertEqual(self.read('openwiki/.last-update.json'), self.baseline)

    def test_partial_page_preserves_baseline(self):
        self.write('openwiki/quickstart.md', '# Updated\n')
        self.assertEqual(self.prepare('failure')['has-pages'], 'true')
        self.assertEqual(self.read('openwiki/.last-update.json'), self.baseline)
        self.assertEqual(self.git('diff', '--cached', '--name-only').strip(), 'openwiki/quickstart.md')

    def test_success_page_keeps_new_baseline(self):
        self.write('openwiki/quickstart.md', '# Updated\n')
        self.assertEqual(self.prepare('success')['has-pages'], 'true')
        self.assertNotEqual(self.read('openwiki/.last-update.json'), self.baseline)

    def test_untracked_nested_page_and_optional_claude(self):
        self.write('openwiki/new/page.md', '# New\n')
        self.write('CLAUDE.md', 'Instructions\n')
        result = self.prepare('failure')
        self.assertEqual(result['has-pages'], 'true')
        self.assertIn('CLAUDE.md', result['list'])
        self.assertIn('openwiki/new/page.md', self.git('diff', '--cached', '--name-only'))

    def test_page_deletion(self):
        (self.root / 'openwiki/quickstart.md').unlink()
        self.assertEqual(self.prepare('failure')['has-pages'], 'true')

    def test_metadata_and_instructions_do_not_qualify(self):
        self.write('openwiki/.claims/new.json', '{}\n')
        self.write('AGENTS.md', 'Changed\n')
        result = self.prepare('failure')
        self.assertEqual(result['has-pages'], 'false')
        self.assertNotIn('CLAUDE.md', result['list'])
        self.assertEqual(self.git('diff', '--cached'), '')
        self.assertFalse((self.root / 'openwiki/.claims/new.json').exists())
        self.assertEqual(self.read('AGENTS.md'), 'Original instructions\n')

    def test_first_failed_run_does_not_add_interrupted_baseline(self):
        self.git('rm', 'openwiki/.last-update.json')
        self.git('commit', '-qm', 'No previous baseline')
        self.write('openwiki/new.md', '# New\n')
        self.assertEqual(self.prepare('failure')['has-pages'], 'true')
        self.assertFalse((self.root / 'openwiki/.last-update.json').exists())


if __name__ == '__main__':
    unittest.main()
