import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(
    os.name == "nt" and Path("build/test_native_process.exe").exists(),
    "Build Windows process fixtures first",
)
class ProcessMonitorTests(unittest.TestCase):
    def probe(self, spec):
        return subprocess.run(
            [str(Path("build/hwtrace.exe").resolve()), "--process-present", spec],
            check=False,
            capture_output=True,
        ).returncode

    def test_invalid_list(self):
        self.assertEqual(self.probe("TM5.exe,"), 2)

    def test_exact_names_and_optimized_binary_without_launcher(self):
        with tempfile.TemporaryDirectory(prefix="hwtrace-process-") as temp:
            root = Path(temp)
            binaries = root / "Binaries"
            binaries.mkdir()
            # This fixture only sleeps. No stress program is executed.
            launcher = root / "y-cruncher.exe"
            shutil.copyfile("build/test_native_process.exe", launcher)
            worker = binaries / "24-ZN5 ~ Fixture.exe"
            shutil.copyfile(launcher, worker)
            exact = root / "HWTrace-unique-fixture.exe"
            shutil.copyfile(launcher, exact)
            self.assertEqual(self.probe(exact.name), 1)
            process = subprocess.Popen([str(exact), "--hold"])
            try:
                self.assertEqual(self.probe(exact.name.upper()), 0)
                self.assertEqual(self.probe("absent-fixture.exe," + exact.name), 0)
                self.assertEqual(self.probe("HWTrace-unique-fixtur.exe"), 1)
            finally:
                process.terminate()
                process.wait(timeout=5)
            baseline = self.probe("y-cruncher.exe")
            self.assertEqual(
                baseline, 1, "A real local y-cruncher would invalidate the fixture"
            )
            process = subprocess.Popen([str(worker), "--hold"])
            try:
                self.assertEqual(self.probe("y-cruncher.exe"), 0)
                self.assertEqual(self.probe("TM5.exe,y-cruncher.exe"), 0)
                # Same native detector used by startup capture, without capturing a desktop.
                command = (
                    ". ./Startup-Capture.ps1; "
                    "if (-not (Get-MonitoredProcessPresent -ProcessName 'y-cruncher.exe')) { exit 9 }"
                )
                subprocess.run(["pwsh", "-NoProfile", "-Command", command], check=True)
                launcher.unlink()
                self.assertEqual(self.probe("y-cruncher.exe"), 1)
                shutil.copyfile("build/test_native_process.exe", launcher)
            finally:
                process.terminate()
                process.wait(timeout=5)
            # A similarly named binary outside Binaries is not a y-cruncher worker.
            unrelated = root / worker.name
            shutil.copyfile(worker, unrelated)
            process = subprocess.Popen([str(unrelated), "--hold"])
            try:
                self.assertEqual(self.probe("y-cruncher.exe"), 1)
            finally:
                process.terminate()
                process.wait(timeout=5)
            process = subprocess.Popen([str(launcher), "--hold"])
            try:
                self.assertEqual(self.probe("y-cruncher.exe"), 0)
            finally:
                process.terminate()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
