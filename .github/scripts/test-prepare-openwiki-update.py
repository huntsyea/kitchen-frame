"""Exercise publication decisions in disposable Git repositories, without inference."""
import os
import json
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

    def prepare(self, outcome, status=None):
        self.write('openwiki/.last-update.json', json.dumps({
            'status': status or ('complete' if outcome == 'success' else 'interrupted'),
            'gitHead': 'new' if outcome == 'success' else 'previous',
        }) + '\n')
        self.write('openwiki/.run.json', '{}\n')
        output = self.root / 'outputs'
        subprocess.run(['bash', str(SCRIPT), outcome], cwd=self.root,
                       env={**os.environ, 'GITHUB_OUTPUT': str(output)}, check=True,
                       capture_output=True, text=True)
        self.assertFalse((self.root / 'openwiki/.run.json').exists())
        return dict(line.split('=', 1) for line in output.read_text().splitlines())

    def test_failure_status_only(self):
        self.assertEqual(self.prepare('failure')['has-changes'], 'false')
        self.assertEqual(self.read('openwiki/.last-update.json'), self.baseline)
        self.assertEqual(self.git('diff', '--cached'), '')

    def test_success_status_only(self):
        self.assertEqual(self.prepare('success')['has-changes'], 'true')
        self.assertEqual(json.loads(self.read('openwiki/.last-update.json'))['status'], 'complete')
        self.assertEqual(self.git('diff', '--cached', '--name-only').strip(), 'openwiki/.last-update.json')

    def test_partial_page_preserves_interrupted_status(self):
        self.write('openwiki/quickstart.md', '# Updated\n')
        self.assertEqual(self.prepare('failure')['has-changes'], 'true')
        metadata = json.loads(self.read('openwiki/.last-update.json'))
        self.assertEqual(metadata['status'], 'interrupted')
        self.assertEqual(metadata['gitHead'], 'previous')
        self.assertIn('openwiki/quickstart.md', self.git('diff', '--cached', '--name-only'))

    def test_success_page_keeps_new_baseline(self):
        self.write('openwiki/quickstart.md', '# Updated\n')
        self.assertEqual(self.prepare('success')['has-changes'], 'true')
        self.assertNotEqual(self.read('openwiki/.last-update.json'), self.baseline)

    def test_untracked_nested_page_and_optional_claude(self):
        self.write('openwiki/new/page.md', '# New\n')
        self.write('CLAUDE.md', 'Instructions\n')
        result = self.prepare('failure')
        self.assertEqual(result['has-changes'], 'true')
        self.assertIn('CLAUDE.md', result['list'])
        self.assertIn('openwiki/new/page.md', self.git('diff', '--cached', '--name-only'))

    def test_page_deletion(self):
        (self.root / 'openwiki/quickstart.md').unlink()
        self.assertEqual(self.prepare('failure')['has-changes'], 'true')

    def test_claims_and_manifest_only_output_is_preserved(self):
        self.write('openwiki/.claims/new.json', '{}\n')
        self.write('openwiki/.page-manifest.json', '{}\n')
        result = self.prepare('failure')
        self.assertEqual(result['has-changes'], 'true')
        self.assertNotIn('CLAUDE.md', result['list'])
        self.assertTrue((self.root / 'openwiki/.claims/new.json').exists())
        self.assertEqual(json.loads(self.read('openwiki/.last-update.json'))['status'], 'interrupted')

    def test_managed_instructions_are_valid_output(self):
        self.write('AGENTS.md', 'Changed\n')
        self.assertEqual(self.prepare('success')['has-changes'], 'true')
        self.assertEqual(self.read('AGENTS.md'), 'Changed\n')

    def test_first_failed_run_with_page_keeps_interrupted_metadata(self):
        self.git('rm', 'openwiki/.last-update.json')
        self.git('commit', '-qm', 'No previous baseline')
        self.write('openwiki/new.md', '# New\n')
        self.assertEqual(self.prepare('failure')['has-changes'], 'true')
        self.assertEqual(json.loads(self.read('openwiki/.last-update.json'))['status'], 'interrupted')

    def test_first_failed_status_only_run_is_discarded(self):
        self.git('rm', 'openwiki/.last-update.json')
        self.git('commit', '-qm', 'No previous baseline')
        self.assertEqual(self.prepare('failure')['has-changes'], 'false')
        self.assertFalse((self.root / 'openwiki/.last-update.json').exists())

    def test_successful_retry_can_clear_interrupted_status_without_page_changes(self):
        self.write('openwiki/.last-update.json', '{"status":"interrupted"}\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'Interrupted baseline')
        self.assertEqual(self.prepare('success')['has-changes'], 'true')
        self.assertEqual(json.loads(self.read('openwiki/.last-update.json'))['status'], 'complete')

    def test_zero_exit_with_interrupted_status_only_is_discarded(self):
        self.assertEqual(self.prepare('success', status='interrupted')['has-changes'], 'false')
        self.assertEqual(self.read('openwiki/.last-update.json'), self.baseline)

    def test_zero_exit_with_interrupted_durable_output_is_preserved(self):
        self.write('openwiki/.page-manifest.json', '{}\n')
        self.assertEqual(self.prepare('success', status='interrupted')['has-changes'], 'true')
        self.assertEqual(json.loads(self.read('openwiki/.last-update.json'))['status'], 'interrupted')


if __name__ == '__main__':
    unittest.main()
