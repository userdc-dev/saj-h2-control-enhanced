"""Offline installation smoke tests: only ONE GitHub archive for both components."""
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"


class SingleRepositoryInstallTests(unittest.TestCase):
    def test_install_upgrade_and_preserve_existing_monitor(self):
        with tempfile.TemporaryDirectory(prefix="saj-installer-") as folder:
            root = Path(folder)
            ha_config = root / "ha_config"
            ha_config.mkdir()
            initial_yaml = "homeassistant:\n  name: Keep this unchanged\n"
            (ha_config / "configuration.yaml").write_text(initial_yaml)
            source_repo = root / "source" / "saj-h2-control-enhanced-main"
            control_src = source_repo / "custom_components" / "saj_h2_control_enhanced"
            safe_src = source_repo / "bundled_components" / "saj_h2_safe"
            for source, domain in ((control_src, "saj_h2_control_enhanced"),
                                   (safe_src, "saj_h2_safe")):
                source.mkdir(parents=True)
                (source / "manifest.json").write_text(
                    json.dumps({"domain": domain, "version": "test"})
                )
                (source / "__init__.py").write_text("# bundled test integration\n")
                (source / "code.txt").write_text("new version\n")
            for name in ("const.py", "sensor.py", "solar_forecast.py",
                         "solar_model.py"):
                (safe_src / name).write_text("# bundled monitor component\n")

            tar_path = root / "one-repo.tar.gz"
            with tarfile.open(tar_path, "w:gz") as archive:
                archive.add(source_repo, arcname="saj-h2-control-enhanced-main")
            curl_dir = root / "bin"
            curl_dir.mkdir()
            curl = curl_dir / "curl"
            curl.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib, shutil, sys\n"
                "args=sys.argv\n"
                "url=next(v for v in args if v.startswith('https://'))\n"
                "expected='https://github.com/userdc-dev/"
                "saj-h2-control-enhanced/archive/refs/heads/main.tar.gz'\n"
                "if url != expected: raise RuntimeError('External repo requested! '+url)\n"
                "shutil.copyfile(os.environ['ONE_ARCHIVE'], "
                "args[args.index('--output')+1])\n"
                "with open(os.environ['CURL_CALLS'],'a') as stream: "
                "stream.write(url+'\\n')\n"
            )
            curl.chmod(curl.stat().st_mode | stat.S_IXUSR)
            calls = root / "curl_calls.txt"
            env = dict(os.environ)
            env["PATH"] = str(curl_dir) + os.pathsep + env.get("PATH", "")
            env["ONE_ARCHIVE"] = str(tar_path)
            env["CURL_CALLS"] = str(calls)

            def install(*options):
                return subprocess.run(
                    ["bash", str(INSTALLER), str(ha_config), *options],
                    capture_output=True, text=True, check=True, env=env
                )

            first = install()
            self.assertIn("Installed bundled SAJ H2 Safe Monitor", first.stdout)
            self.assertIn("Installed/updated SAJ H2 Control Enhanced", first.stdout)
            control = ha_config / "custom_components" / "saj_h2_control_enhanced"
            safe = ha_config / "custom_components" / "saj_h2_safe"
            self.assertTrue((control / "manifest.json").is_file())
            self.assertTrue((safe / "solar_forecast.py").is_file())
            self.assertEqual((ha_config / "configuration.yaml").read_text(), initial_yaml)
            self.assertEqual(len(calls.read_text().splitlines()), 1)

            (control / "code.txt").write_text("previous custom control version\n")
            (safe / "code.txt").write_text("DO NOT CHANGE EXISTING SAFE MONITOR\n")
            second = install()
            self.assertIn("preserving it unchanged", second.stdout)
            self.assertEqual((control / "code.txt").read_text(), "new version\n")
            self.assertEqual((safe / "code.txt").read_text(),
                             "DO NOT CHANGE EXISTING SAFE MONITOR\n")
            backups = list((ha_config / ".saj-h2-backups").glob(
                "*/saj_h2_control_enhanced/code.txt"
            ))
            self.assertTrue(backups)
            self.assertEqual(backups[0].read_text(), "previous custom control version\n")
            self.assertEqual(len(calls.read_text().splitlines()), 2)
            self.assertEqual(
                sorted(p.name for p in (ha_config / "custom_components").iterdir()),
                ["saj_h2_control_enhanced", "saj_h2_safe"]
            )
            self.assertEqual((ha_config / "configuration.yaml").read_text(), initial_yaml)

            third = install("--control-only")
            self.assertIn("Controller-only option selected", third.stdout)
            self.assertEqual((safe / "code.txt").read_text(),
                             "DO NOT CHANGE EXISTING SAFE MONITOR\n")
            self.assertEqual(len(calls.read_text().splitlines()), 3)

    def test_bad_argument_fails_without_install(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                ["bash", str(INSTALLER), folder, "--with-safe-monitor"],
                capture_output=True, text=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Unsupported option", result.stderr)


if __name__ == "__main__":
    unittest.main()
