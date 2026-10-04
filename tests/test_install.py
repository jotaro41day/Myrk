from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("cc") or shutil.which("clang"), "native C compiler required")
class InstallTests(unittest.TestCase):
    def test_reinstall_and_run_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "prefix"
            for _ in range(2):
                subprocess.run([str(ROOT / "install.sh"), "--prefix", str(prefix)],
                               cwd=directory, check=True, capture_output=True, text=True)
            launcher = prefix / "bin" / "myrk"
            version = subprocess.run([str(launcher), "--version"], cwd=directory,
                                     check=True, capture_output=True, text=True)
            self.assertIn("myrk 0.1.0", version.stdout)
            result = subprocess.run([str(launcher), "run", str(ROOT / "examples/hello.myrk")],
                                    cwd=directory, check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, "42\n")


if __name__ == "__main__":
    unittest.main()
