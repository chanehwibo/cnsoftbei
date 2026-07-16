import tempfile
import unittest
from pathlib import Path
from unittest import mock

from safeops_agent import config


class PackagedResourceTest(unittest.TestCase):
    def test_runtime_defaults_and_web_assets_are_bundled(self):
        for name in ("app.yaml", "policy.yaml", "tools.yaml", "llm.yaml"):
            self.assertTrue((config.BUNDLED_CONFIG_DIR / name).is_file(), name)
        for name in ("index.html", "styles.css", "app_logic.js", "app.js"):
            self.assertTrue((config.BUNDLED_WEB_ROOT / name).is_file(), name)

    def test_config_loader_falls_back_to_bundled_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(config, "LOCAL_CONFIG_DIR", Path(directory) / "config"):
                self.assertEqual(config.load_app_config()["web_port"], 8765)
                self.assertIn("destructive_keywords", config.load_policy_config())
                self.assertIn("service_allowlist", config.load_tools_config())
                self.assertEqual(config.load_llm_config()["llm_provider"], "deepseek")

    def test_bundled_resources_match_source_files(self):
        source_root = Path(__file__).resolve().parents[1]
        for group, names in {
            "config": ("app.yaml", "policy.yaml", "tools.yaml", "llm.yaml"),
            "web": ("index.html", "styles.css", "app_logic.js", "app.js"),
        }.items():
            for name in names:
                source = (source_root / group / name).read_text(encoding="utf-8").splitlines()
                bundled = (config.BUNDLED_RESOURCE_ROOT / group / name).read_text(
                    encoding="utf-8"
                ).splitlines()
                self.assertEqual(bundled, source, f"{group}/{name} 未同步到包内资源")


if __name__ == "__main__":
    unittest.main()
