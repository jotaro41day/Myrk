from pathlib import Path
import math
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
            for model,count,fields in [('if',6000,2),('lif',5000,2),('qif',1000,2),
                                       ('izhikevich',3000,3),('adex',3000,3),('hh',1000,5)]:
                with self.subTest(model=model):
                    result=subprocess.run([str(launcher),'run',str(ROOT/f'examples/{model}.myrk')],
                        cwd=directory,check=True,capture_output=True,text=True)
                    values=result.stdout.splitlines()
                    self.assertEqual(len(values),fields)
                    self.assertEqual(int(values[0]),count)
                    self.assertTrue(all(math.isfinite(float(v)) for v in values[1:]))


if __name__ == "__main__":
    unittest.main()
