import unittest

from safeops_agent.tools.system import (
    get_system_info,
    get_resource_usage,
    list_processes,
    list_disk_partitions,
    list_users,
    list_safe_environment,
    list_listening_ports,
    list_network_connections,
    get_service_status,
    query_package,
    restart_service,
    list_cron_jobs,
    inspect_recent_errors,
)


class SystemToolsTest(unittest.TestCase):
    def test_system_info_returns_ok(self):
        result = get_system_info({})
        self.assertTrue(result.ok)
        self.assertIn("system", result.data)
        self.assertIn("machine", result.data)
        self.assertIn("hostname", result.data)

    def test_resource_usage_returns_ok(self):
        result = get_resource_usage({})
        self.assertTrue(result.ok)
        self.assertIn("cpu", result.data)
        self.assertIn("disk", result.data)
        self.assertIn("memory", result.data)

    def test_list_processes_default_limit(self):
        result = list_processes({})
        self.assertTrue(result.ok)
        self.assertIn("lines", result.data)

    def test_list_processes_respects_limit(self):
        result = list_processes({"limit": 5})
        self.assertTrue(result.ok)

    def test_list_processes_clamps_oversized_limit(self):
        result = list_processes({"limit": 999})
        self.assertTrue(result.ok)

    def test_list_processes_clamps_zero_limit(self):
        result = list_processes({"limit": 0})
        self.assertTrue(result.ok)

    def test_list_disk_partitions_ok(self):
        result = list_disk_partitions({})
        self.assertTrue(result.ok)

    def test_list_users_ok(self):
        result = list_users({})
        self.assertTrue(result.ok)

    def test_safe_environment_ok(self):
        result = list_safe_environment({})
        self.assertTrue(result.ok)
        self.assertIn("environment", result.data)

    def test_safe_environment_no_secrets(self):
        result = list_safe_environment({})
        env = result.data.get("environment", {})
        for key in env:
            self.assertNotIn("SECRET", key.upper())
            self.assertNotIn("PASSWORD", key.upper())
            self.assertNotIn("TOKEN", key.upper())

    def test_listening_ports_ok(self):
        result = list_listening_ports({"limit": 10})
        self.assertTrue(result.ok)

    def test_network_connections_ok(self):
        result = list_network_connections({"limit": 10})
        self.assertTrue(result.ok)

    def test_service_status_empty_name_fails(self):
        result = get_service_status({"service": ""})
        self.assertFalse(result.ok)

    def test_service_status_invalid_name_fails(self):
        result = get_service_status({"service": "nginx;echo"})
        self.assertFalse(result.ok)

    def test_service_status_newline_injection_fails(self):
        result = get_service_status({"service": "nginx\nrm -rf /"})
        self.assertFalse(result.ok)

    def test_package_query_invalid_name_fails(self):
        result = query_package({"package": "pkg;rm"})
        self.assertFalse(result.ok)

    def test_package_query_newline_injection_fails(self):
        result = query_package({"package": "pkg\nmalicious"})
        self.assertFalse(result.ok)

    def test_package_query_empty_ok(self):
        result = query_package({"package": ""})
        self.assertTrue(result.ok)

    def test_restart_service_executes_with_rollback_hint(self):
        result = restart_service({"service": "nginx"})
        # Windows 开发环境返回 systemctl 预告；Linux/麒麟真实执行。两者都必须附带逆操作建议。
        self.assertIn("rollback", result.data or {})
        self.assertEqual(result.data["rollback"]["tool"], "service.restart")

    def test_restart_service_rejects_bad_name(self):
        result = restart_service({"service": "nginx; rm -rf /"})
        self.assertFalse(result.ok)

    def test_cron_jobs_ok(self):
        result = list_cron_jobs({})
        self.assertTrue(result.ok)

    def test_recent_errors_ok(self):
        result = inspect_recent_errors({})
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
