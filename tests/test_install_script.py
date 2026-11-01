"""Offline install-script smoke test. No network, no HA, no inverter touched."""
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


class ZeroYamlInstallTests(unittest.TestCase):
    def test_install_optional_monitor_and_upgrade_without_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="saj-installer-") as folder:
            t = Path(folder)
            config = t / "ha_config"
            config.mkdir()
            (config / "configuration.yaml").write_text("homeassistant:\n  name: Preserved\n")
            bin_dir = t / "bin"
            bin_dir.mkdir()
            for repo, domain in (
                ("saj-h2-control-enhanced", "saj_h2_control_enhanced"),
                ("saj-h2-safe-enhanced", "saj_h2_safe"),
            ):
                staged = t / "staged" / (repo + "-main") / "custom_components" / domain
                staged.mkdir(parents=True, exist_ok=True)
                (staged / "manifest.json").write_text(
                    json.dumps({"domain": domain, "version": "test"})
                )
                (staged / "__init__.py").write_text("# test only\n")
                (staged / "code.txt").write_text("version-new\n")
                with tarfile.open(t / (repo + ".tar.gz"), "w:gz") as tar:
                    tar.add(t / "staged" / (repo + "-main"), arcname=repo + "-main")

            curl = bin_dir / "curl"
            curl.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib, shutil, sys\n"
                "a=sys.argv\n"
                "url=next(x for x in a if x.startswith('https://'))\n"
                "name=url.split('/')[4]\n"
                "shutil.copyfile(pathlib.Path(os.environ['TEST_ARCHIVES'])/(name+'.tar.gz'),"
                "a[a.index('--output')+1])\n"
            )
            curl.chmod(curl.stat().st_mode | stat.S_IXUSR)

            env = dict(os.environ)
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
            env["TEST_ARCHIVES"] = str(t)
            def install(*flags):
                return subprocess.run(
                    ["bash", str(INSTALLER), str(config), *flags],
                    capture_output=True, text=True, check=True, env=env
                )

            first = install("--with-safe-monitor")
            self.assertIn("Installed saj_h2_control_enhanced", first.stdout)
            self.assertIn("Installed saj_h2_safe", first.stdout)
            controls = config / "custom_components" / "saj_h2_control_enhanced"
            monitor = config / "custom_components" / "saj_h2_safe"
            self.assertTrue((controls / "manifest.json").is_file())
            self.assertTrue((monitor / "manifest.json").is_file())
            self.assertEqual((config / "configuration.yaml").read_text(),
                             "homeassistant:\n  name: Preserved\n")

            (controls / "code.txt").write_text("version-old\n")
            (monitor / "code.txt").write_text("SAFE EXISTING MONITOR, DO NOT EDIT\n")
            second = install("--with-safe-monitor")
            self.assertIn("Preserving existing independent saj_h2_safe", second.stdout)
            self.assertEqual((controls / "code.txt").read_text(), "version-new\n")
            self.assertEqual((monitor / "code.txt").read_text(),
                             "SAFE EXISTING MONITOR, DO NOT EDIT\n")
            backups = list((config / ".saj-h2-backups").glob("*/saj_h2_control_enhanced/code.txt"))
            self.assertTrue(backups, "Existing control code should be backed up")
            self.assertEqual(backups[0].read_text(), "version-old\n")
            actual_dirs = sorted(p.name for p in (config / "custom_components").iterdir())
            self.assertEqual(actual_dirs, ["saj_h2_control_enhanced", "saj_h2_safe"])
            self.assertEqual((config / "configuration.yaml").read_text(),
                             "homeassistant:\n  name: Preserved\n")


if __name__ == "__main__":
    unittest.main()
