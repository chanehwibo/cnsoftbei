import unittest
from unittest import mock

from safeops_agent.tools import diagnostics
from safeops_agent.tools.models import ToolResult


class EvidenceDrivenDiagnosticsTest(unittest.TestCase):
    def test_resources_only_report_thresholds_that_are_exceeded(self):
        collected = ToolResult(
            ok=True,
            summary="collected",
            data={
                "cpu": {"cpu_count": 4, "load_average": {"1m": 4.2, "5m": 3.0, "15m": 2.0}},
                "memory": {"used_percent": 92},
                "disk": {"used_percent": 70},
            },
        )
        with mock.patch.object(diagnostics, "get_resource_usage", return_value=collected):
            report = diagnostics.diagnose_resources({}).data["diagnosis"]

        self.assertEqual(report["severity"], "critical")
        self.assertTrue(any("CPU" in item for item in report["possible_causes"]))
        self.assertTrue(any("内存" in item for item in report["possible_causes"]))
        self.assertFalse(any("根分区" in item for item in report["possible_causes"]))

    def test_healthy_resources_do_not_return_fixed_failure_hypotheses(self):
        collected = ToolResult(
            ok=True,
            summary="collected",
            data={
                "cpu": {"cpu_count": 8, "load_average": {"1m": 1.0}},
                "memory": {"used_percent": 40},
                "disk": {"used_percent": 50},
            },
        )
        with mock.patch.object(diagnostics, "get_resource_usage", return_value=collected):
            report = diagnostics.diagnose_resources({}).data["diagnosis"]

        self.assertEqual(report["severity"], "healthy")
        self.assertIn("未发现明确资源瓶颈", report["possible_causes"][0])

    def test_disk_diagnosis_computes_partition_percentages(self):
        collected = ToolResult(
            ok=True,
            summary="collected",
            data={"partitions": [{"mount": "D:/", "total_bytes": 1000, "used_bytes": 960}]},
        )
        with mock.patch.object(diagnostics, "list_disk_partitions", return_value=collected):
            report = diagnostics.diagnose_disk({}).data["diagnosis"]

        self.assertEqual(report["severity"], "critical")
        self.assertIn("96.0%", report["possible_causes"][0])

    def test_target_port_is_matched_against_collected_lines(self):
        collected = ToolResult(
            ok=True,
            summary="collected",
            data={"lines": ["TCP 0.0.0.0:8765 0.0.0.0:0 LISTENING 42"]},
        )
        with mock.patch.object(diagnostics, "list_listening_ports", return_value=collected):
            occupied = diagnostics.diagnose_network_ports({"port": 8765}).data["diagnosis"]
            free = diagnostics.diagnose_network_ports({"port": 9000}).data["diagnosis"]

        self.assertEqual(occupied["severity"], "warning")
        self.assertEqual(len(occupied["evidence"]["matched_lines"]), 1)
        self.assertEqual(free["severity"], "healthy")

    def test_service_failure_is_classified_from_actual_status_output(self):
        collected = ToolResult(
            ok=False,
            summary="query failed",
            data={"service": "nginx"},
            error="Active: failed (Result: exit-code)",
        )
        with mock.patch.object(diagnostics, "get_service_status", return_value=collected):
            result = diagnostics.diagnose_service({"service": "nginx"})

        self.assertFalse(result.ok)
        report = result.data["diagnosis"]
        self.assertEqual(report["severity"], "critical")
        self.assertIn("启动失败", report["possible_causes"][0])

    def test_logs_only_recommend_actions_for_detected_signatures(self):
        collected = ToolResult(
            ok=True,
            summary="collected",
            data={"output": "kernel: Out of memory: Killed process 42\napp: Permission denied /srv/data"},
        )
        with mock.patch.object(diagnostics, "inspect_recent_errors", return_value=collected):
            report = diagnostics.diagnose_logs({}).data["diagnosis"]

        self.assertEqual(report["severity"], "critical")
        self.assertTrue(any("OOM" in item for item in report["possible_causes"]))
        self.assertTrue(any("权限" in item for item in report["possible_causes"]))
        self.assertFalse(any("磁盘空间耗尽" in item for item in report["possible_causes"]))


if __name__ == "__main__":
    unittest.main()
