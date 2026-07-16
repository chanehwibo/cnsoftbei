import json
import tempfile
import unittest
from pathlib import Path

from safeops_agent.agent import SafeOpsAgent
from safeops_agent.audit.logger import AuditLogger
from safeops_agent.llm import RuleBasedProvider
from safeops_agent.security.policy import PolicyEngine


class InputLengthTest(unittest.TestCase):
    def make_agent(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return SafeOpsAgent(
            audit_logger=AuditLogger(Path(temp_dir.name) / "audit.log"),
            llm=RuleBasedProvider(),
        )

    def test_rejects_oversized_input(self):
        agent = self.make_agent()
        response = agent.handle("a" * 2001)
        self.assertFalse(response.ok)
        self.assertIn("输入过长", response.message)

    def test_accepts_max_length_input(self):
        agent = self.make_agent()
        long_text = "查看系统信息" + "a" * 1990
        response = agent.handle(long_text)
        self.assertNotIn("输入过长", response.message)


class ContextResolutionTest(unittest.TestCase):
    def make_agent(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return SafeOpsAgent(
            audit_logger=AuditLogger(Path(temp_dir.name) / "audit.log"),
            llm=RuleBasedProvider(),
        )

    def test_resolves_pronoun_after_service_query(self):
        agent = self.make_agent()
        agent.handle("查看 nginx 服务状态")
        self.assertEqual(agent._last_service, "nginx")
        resolved = agent._resolve_context("重启它")
        self.assertIn("nginx", resolved)
        self.assertNotIn("它", resolved)

    def test_resolves_named_reference(self):
        agent = self.make_agent()
        agent._last_service = "redis"
        resolved = agent._resolve_context("重启该服务")
        self.assertEqual(resolved, "重启redis")

    def test_no_resolution_without_context(self):
        agent = self.make_agent()
        resolved = agent._resolve_context("重启它")
        self.assertEqual(resolved, "重启它")

    def test_no_resolution_without_service_keyword(self):
        agent = self.make_agent()
        agent._last_service = "nginx"
        resolved = agent._resolve_context("它很好用")
        self.assertEqual(resolved, "它很好用")


class ServiceNameExtractionTest(unittest.TestCase):
    def make_agent(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return SafeOpsAgent(
            audit_logger=AuditLogger(Path(temp_dir.name) / "audit.log"),
            llm=RuleBasedProvider(),
        )

    def test_extracts_known_service(self):
        agent = self.make_agent()
        self.assertEqual(agent._extract_service_name("查看 nginx 服务状态"), "nginx")

    def test_prefers_longer_match(self):
        agent = self.make_agent()
        self.assertEqual(agent._extract_service_name("查看 redis-server 状态"), "redis-server")

    def test_extracts_unknown_service_by_token(self):
        agent = self.make_agent()
        self.assertEqual(agent._extract_service_name("查看 myapp 服务状态"), "myapp")

    def test_returns_empty_for_no_service(self):
        agent = self.make_agent()
        self.assertEqual(agent._extract_service_name("查看 服务 状态"), "")


class ToolPriorityTest(unittest.TestCase):
    def make_agent(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return SafeOpsAgent(
            audit_logger=AuditLogger(Path(temp_dir.name) / "audit.log"),
            llm=RuleBasedProvider(),
        )

    def test_disk_partition_not_confused_with_resources(self):
        agent = self.make_agent()
        response = agent.handle("查看磁盘分区")
        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "disk.partitions")

    def test_disk_usage_routes_to_resources(self):
        agent = self.make_agent()
        response = agent.handle("查看磁盘使用")
        self.assertTrue(response.ok)
        self.assertEqual(response.tool, "system.resources")


class OfflineOperationRoutingTest(unittest.TestCase):
    def setUp(self):
        self.agent = SafeOpsAgent(llm=RuleBasedProvider())

    def test_routes_service_start(self):
        tool, args = self.agent._select_tool("启动 nginx 服务")
        self.assertEqual(tool, "service.start")
        self.assertEqual(args, {"service": "nginx"})

    def test_routes_service_stop(self):
        tool, args = self.agent._select_tool("停止 nginx 服务")
        self.assertEqual(tool, "service.stop")
        self.assertEqual(args, {"service": "nginx"})

    def test_routes_managed_file_apply(self):
        tool, args = self.agent._select_tool("写入受管文件 app.conf 内容为 port=8080")
        self.assertEqual(tool, "file.apply")
        self.assertEqual(args, {"name": "app.conf", "content": "port=8080"})

    def test_routes_managed_file_rollback(self):
        tool, args = self.agent._select_tool("回滚受管文件到快照 app.conf.123")
        self.assertEqual(tool, "file.rollback")
        self.assertEqual(args, {"snapshot_id": "app.conf.123"})

    def test_routes_managed_file_list(self):
        tool, args = self.agent._select_tool("查看受管文件列表")
        self.assertEqual(tool, "file.list_managed")
        self.assertEqual(args, {})

    def test_agent_uses_configured_tool_defaults(self):
        self.agent._tool_defaults = {
            "process_limit": 7,
            "network_limit": 11,
            "log_lines": 23,
        }
        self.assertEqual(self.agent._select_tool("查看进程")[1]["limit"], 7)
        self.assertEqual(self.agent._select_tool("查看监听端口")[1]["limit"], 11)
        self.assertEqual(self.agent._select_tool("查看错误日志")[1]["lines"], 23)


class AsciiKeywordBoundaryTest(unittest.TestCase):
    def test_rejects_standalone_reboot(self):
        engine = PolicyEngine()
        decision = engine.evaluate_intent("reboot the server")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_allows_reboot_as_substring(self):
        engine = PolicyEngine()
        decision = engine.evaluate_intent("configure rebootStrategy for pods")
        self.assertIsNone(decision)

    def test_rejects_rm_rf_with_spaces(self):
        engine = PolicyEngine()
        decision = engine.evaluate_intent("please rm -rf /tmp")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)

    def test_allows_halt_in_word(self):
        engine = PolicyEngine()
        decision = engine.evaluate_intent("查看 halting problem 相关配置")
        self.assertIsNone(decision)

    def test_rejects_standalone_shutdown(self):
        engine = PolicyEngine()
        decision = engine.evaluate_intent("run shutdown now")
        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)


class AuditLogRotationTest(unittest.TestCase):
    def test_rotates_when_exceeds_max_size(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        log_path = Path(temp_dir.name) / "audit.log"

        logger = AuditLogger(log_path)
        logger.MAX_FILE_SIZE = 1024

        for i in range(50):
            logger.record({"event": f"test_{i}", "padding": "x" * 100})

        self.assertTrue(log_path.exists())
        backup = log_path.with_suffix(".log.1")
        self.assertTrue(backup.exists())
        self.assertLess(log_path.stat().st_size, 2048)
        report = logger.verify()
        self.assertTrue(report["ok"], msg=str(report))
        self.assertGreater(report["segments"], 1)

    def test_recent_works_after_rotation(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        log_path = Path(temp_dir.name) / "audit.log"

        logger = AuditLogger(log_path)
        logger.MAX_FILE_SIZE = 512

        for i in range(30):
            logger.record({"index": i, "padding": "x" * 80})

        events = logger.recent(5)
        self.assertGreater(len(events), 0)
        self.assertLessEqual(len(events), 5)
        for event in events:
            self.assertIn("index", event)


if __name__ == "__main__":
    unittest.main()
