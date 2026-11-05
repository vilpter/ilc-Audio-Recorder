"""artifact_detector must import and degrade cleanly when numpy is missing."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BLOCK_NUMPY = """
import sys
class _Block:
    def find_spec(self, name, path=None, target=None):
        if name == 'numpy' or name.startswith('numpy.'):
            raise ImportError('numpy blocked for test')
sys.meta_path.insert(0, _Block())
import artifact_detector
assert artifact_detector.NUMPY_AVAILABLE is False
result = artifact_detector.detect_artifacts('/nonexistent.wav')
print(result.error_message)
"""


def test_imports_and_reports_without_numpy():
    proc = subprocess.run([sys.executable, '-c', BLOCK_NUMPY], cwd=ROOT,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert 'NumPy not installed' in proc.stdout
