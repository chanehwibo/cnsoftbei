import tempfile
import unittest
from pathlib import Path

from safeops_agent.config import CONFIG_DIR
from safeops_agent.config import load_simple_yaml
from safeops_agent.config_check import validate_configs

SERVICE_GUARDS = "service_allowlist:\n  - nginx\nprotected_services:\n  - auditd\n"


def write_config(directory: Path, name: str, content: str) -> None:
    (directory / name).write_text(content, encoding="utf-8")


def write_valid_configs(directory: Path) -> None:
    write_config(directory, "app.yaml", "audit_log: data/audit.log\nweb_host: 127.0.0.1\nweb_port: 8765\n")
    write_config(directory, "policy.yaml", "destructive_keywords:\n  - rm -rf\nsensitive_paths:\n  - /etc\n")
    write_config(
        directory,
        "tools.yaml",
        "disabled_tools:\ntool_defaults:\n  process_limit: 10\n" + SERVICE_GUARDS,
    )
    write_config(
        directory,
        "llm.yaml",
        'llm_enabled: false\nllm_provider: deepseek\nllm_model: demo\nllm_api_key: ""\n'
        "llm_base_url: https://api.deepseek.com/v1\nllm_timeout: 8\n",
    )


class ConfigCheckTest(unittest.TestCase):
    def test_standard_yaml_preserves_nested_tool_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "tools.yaml"
            path.write_text("tool_defaults:\n  process_limit: 7\n", encoding="utf-8")
            parsed = load_simple_yaml(path)
            self.assertEqual(parsed["tool_defaults"]["process_limit"], 7)

    def test_repo_config_passes_validation(self):
        report = validate_configs(CONFIG_DIR)
        self.assertTrue(report["ok"], msg=f"仓库配置应校验通过：{report['errors']}")

    def test_valid_configs_pass(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            report = validate_configs(temp_dir)
            self.assertTrue(report["ok"], msg=str(report["errors"]))
            self.assertEqual(report["errors"], [])

    def test_missing_required_file_is_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            (Path(temp_dir) / "policy.yaml").unlink()
            report = validate_configs(temp_dir)
            self.assertFalse(report["ok"])
            self.assertTrue(any("policy.yaml: 文件缺失" in message for message in report["errors"]))

    def test_invalid_web_port_is_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(Path(temp_dir), "app.yaml", "audit_log: data/audit.log\nweb_host: h\nweb_port: 99999\n")
            report = validate_configs(temp_dir)
            self.assertFalse(report["ok"])
            self.assertTrue(any("web_port" in message for message in report["errors"]))

    def test_remote_web_host_requires_authentication(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(
                Path(temp_dir),
                "app.yaml",
                "audit_log: data/audit.log\nweb_host: 0.0.0.0\nweb_port: 8765\nrequire_auth: false\n",
            )
            report = validate_configs(temp_dir)

            self.assertFalse(report["ok"])
            self.assertTrue(any("非本机回环地址" in message for message in report["errors"]))
            self.assertTrue(any("启用 TLS" in message for message in report["errors"]))

    def test_authentication_can_only_be_disabled_in_explicit_loopback_development_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(
                Path(temp_dir),
                "app.yaml",
                "audit_log: data/audit.log\nweb_host: 127.0.0.1\nweb_port: 8765\nrequire_auth: false\n",
            )
            report = validate_configs(temp_dir)
            self.assertFalse(report["ok"])
            self.assertTrue(any("非开发模式" in message for message in report["errors"]))

            write_config(
                Path(temp_dir),
                "app.yaml",
                "audit_log: data/audit.log\nweb_host: 127.0.0.1\nweb_port: 8765\n"
                "require_auth: false\ndevelopment_mode: true\n",
            )
            report = validate_configs(temp_dir)
            self.assertTrue(report["ok"], msg=str(report["errors"]))

    def test_development_mode_cannot_bind_non_loopback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(
                Path(temp_dir),
                "app.yaml",
                "audit_log: data/audit.log\nweb_host: 0.0.0.0\nweb_port: 8765\n"
                "require_auth: false\ndevelopment_mode: true\ntls_enabled: true\n"
                "tls_cert_file: cert.pem\ntls_key_file: key.pem\n",
            )
            report = validate_configs(temp_dir)
            self.assertFalse(report["ok"])
            self.assertTrue(any("development_mode 仅允许" in message for message in report["errors"]))

    def test_tls_requires_certificate_and_key_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(
                Path(temp_dir),
                "app.yaml",
                "audit_log: data/audit.log\nweb_host: 127.0.0.1\nweb_port: 8765\n"
                "require_auth: true\ntls_enabled: true\ntls_cert_file: ''\ntls_key_file: ''\n",
            )
            report = validate_configs(temp_dir)

            self.assertFalse(report["ok"])
            self.assertTrue(any("tls_cert_file" in message for message in report["errors"]))
            self.assertTrue(any("tls_key_file" in message for message in report["errors"]))

    def test_empty_destructive_keywords_is_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(Path(temp_dir), "policy.yaml", "destructive_keywords: []\nsensitive_paths:\n  - /etc\n")
            report = validate_configs(temp_dir)
            self.assertFalse(report["ok"])
            self.assertTrue(any("destructive_keywords" in message for message in report["errors"]))

    def test_unknown_disabled_tool_is_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(Path(temp_dir), "tools.yaml", "disabled_tools:\n  - no.such_tool\n" + SERVICE_GUARDS)
            report = validate_configs(temp_dir)
            self.assertTrue(report["ok"], msg="未知工具名应是 warning 而非 error")
            self.assertTrue(any("no.such_tool" in message for message in report["warnings"]))

    def test_known_disabled_tool_no_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(Path(temp_dir), "tools.yaml", "disabled_tools:\n  - service.restart\n" + SERVICE_GUARDS)
            report = validate_configs(temp_dir)
            self.assertTrue(report["ok"])
            self.assertFalse(any("service.restart" in message for message in report["warnings"]))

    def test_llm_enabled_without_model_is_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(Path(temp_dir), "llm.yaml", 'llm_enabled: true\nllm_provider: deepseek\nllm_model: ""\n')
            report = validate_configs(temp_dir)
            self.assertFalse(report["ok"])
            self.assertTrue(any("llm_model" in message for message in report["errors"]))

    def test_empty_api_key_when_enabled_is_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(
                Path(temp_dir),
                "llm.yaml",
                'llm_enabled: true\nllm_provider: deepseek\nllm_model: demo\nllm_api_key: ""\n',
            )
            report = validate_configs(temp_dir)
            self.assertTrue(report["ok"])
            self.assertTrue(any("llm_api_key" in message for message in report["warnings"]))

    def test_llm_local_yaml_overrides_llm_yaml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(Path(temp_dir), "llm.yaml", 'llm_enabled: true\nllm_provider: deepseek\nllm_model: ""\n')
            write_config(Path(temp_dir), "llm.local.yaml", "llm_model: demo\nllm_api_key: sk-test\n")
            report = validate_configs(temp_dir)
            self.assertTrue(report["ok"], msg=str(report["errors"]))
            self.assertIn("llm.local.yaml", report["checked_files"])

    def test_negative_tool_default_is_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(
                Path(temp_dir),
                "tools.yaml",
                "disabled_tools:\ntool_defaults:\n  process_limit: -1\n" + SERVICE_GUARDS,
            )
            report = validate_configs(temp_dir)
            self.assertFalse(report["ok"])
            self.assertTrue(any("process_limit" in message for message in report["errors"]))

    def test_service_allowlist_and_protected_services_cannot_overlap(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_valid_configs(Path(temp_dir))
            write_config(
                Path(temp_dir),
                "tools.yaml",
                "disabled_tools:\nservice_allowlist:\n  - nginx\nprotected_services:\n  - nginx\n",
            )
            report = validate_configs(temp_dir)

            self.assertFalse(report["ok"])
            self.assertTrue(any("同时出现在允许和保护列表" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
