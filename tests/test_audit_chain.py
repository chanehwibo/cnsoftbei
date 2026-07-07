import json
import tempfile
import unittest
from pathlib import Path

from safeops_agent.audit.logger import AuditLogger


class AuditHashChainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "audit.log"
        self.logger = AuditLogger(self.path)

    def _write_events(self, count=3):
        for i in range(count):
            self.logger.record({"event_type": "test", "n": i})

    def test_intact_chain_verifies(self):
        self._write_events()
        report = self.logger.verify()
        self.assertTrue(report["ok"])
        self.assertEqual(report["checked"], 3)

    def test_events_carry_chain_fields(self):
        self._write_events(2)
        events = self.logger.recent(2)
        self.assertEqual(events[0]["prev_hash"], AuditLogger.GENESIS_HASH)
        self.assertEqual(events[1]["prev_hash"], events[0]["entry_hash"])

    def test_content_tampering_detected(self):
        self._write_events()
        lines = self.path.read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[1])
        event["n"] = 999  # 改内容但保留原哈希
        lines[1] = json.dumps(event, ensure_ascii=False, sort_keys=True)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report = self.logger.verify()
        self.assertFalse(report["ok"])
        self.assertEqual(report["first_bad_line"], 2)
        self.assertIn("篡改", report["reason"])

    def test_event_deletion_detected(self):
        self._write_events()
        lines = self.path.read_text(encoding="utf-8").splitlines()
        del lines[1]  # 抽掉中间一条
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report = self.logger.verify()
        self.assertFalse(report["ok"])
        self.assertIn("断裂", report["reason"])

    def test_legacy_events_tolerated_at_head(self):
        # 哈希链上线前的旧事件（无哈希字段）只允许出现在文件头部
        self.path.parent.mkdir(parents=True, exist_ok=True)
        legacy = json.dumps({"event_type": "legacy", "ts": "2026-01-01"}, ensure_ascii=False)
        self.path.write_text(legacy + "\n", encoding="utf-8")
        self._write_events(2)

        report = self.logger.verify()
        self.assertTrue(report["ok"])
        self.assertEqual(report["legacy"], 1)
        self.assertEqual(report["checked"], 2)

    def test_empty_log_ok(self):
        report = self.logger.verify()
        self.assertTrue(report["ok"])
        self.assertEqual(report["checked"], 0)


if __name__ == "__main__":
    unittest.main()
