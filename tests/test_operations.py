import unittest
from unittest import mock

from safeops_agent.tools import operations
from safeops_agent.tools.registry import build_registry


class ManagedFileRollbackTest(unittest.TestCase):
    def setUp(self):
        # 将受管/快照根重定向到临时目录，避免污染项目
        import tempfile
        from pathlib import Path
        self._dir = tempfile.TemporaryDirectory()
        root = Path(self._dir.name)
        operations.MANAGED_ROOT = root / "managed"
        operations.SNAPSHOT_ROOT = root / "snapshots"

    def tearDown(self):
        self._dir.cleanup()

    def test_apply_creates_file_and_snapshot(self):
        res = operations.apply_managed_file({"name": "app.conf", "content": "key=1"})
        self.assertTrue(res.ok)
        self.assertIn("snapshot_id", res.data)
        self.assertFalse(res.data["existed_before"])
        target = operations.MANAGED_ROOT / "app.conf"
        self.assertEqual(target.read_text(encoding="utf-8"), "key=1")

    def test_rollback_deletes_newly_created_file(self):
        res = operations.apply_managed_file({"name": "new.conf", "content": "a=1"})
        sid = res.data["snapshot_id"]
        back = operations.rollback_managed_file({"snapshot_id": sid})
        self.assertTrue(back.ok)
        self.assertEqual(back.data["action"], "deleted")
        self.assertFalse((operations.MANAGED_ROOT / "new.conf").exists())

    def test_rollback_restores_previous_content(self):
        operations.apply_managed_file({"name": "svc.conf", "content": "v=1"})
        res2 = operations.apply_managed_file({"name": "svc.conf", "content": "v=2"})
        self.assertTrue(res2.data["existed_before"])
        sid = res2.data["snapshot_id"]
        target = operations.MANAGED_ROOT / "svc.conf"
        self.assertEqual(target.read_text(encoding="utf-8"), "v=2")
        back = operations.rollback_managed_file({"snapshot_id": sid})
        self.assertTrue(back.ok)
        self.assertEqual(back.data["action"], "restored")
        self.assertEqual(target.read_text(encoding="utf-8"), "v=1")

    def test_rejects_path_traversal_name(self):
        for bad in ["../evil", "a/b", "a\\b", ".."]:
            res = operations.apply_managed_file({"name": bad, "content": "x"})
            self.assertFalse(res.ok, bad)

    def test_rejects_oversized_content(self):
        res = operations.apply_managed_file({"name": "big.conf", "content": "x" * (operations.MAX_CONTENT_LENGTH + 1)})
        self.assertFalse(res.ok)

    def test_rejects_oversized_multibyte_content_by_encoded_size(self):
        res = operations.apply_managed_file(
            {"name": "big-utf8.conf", "content": "中" * (operations.MAX_CONTENT_LENGTH // 3 + 1)}
        )
        self.assertFalse(res.ok)

    def test_snapshot_ids_remain_unique_when_clock_is_constant(self):
        with mock.patch.object(operations.time, "time", return_value=1234.5):
            first = operations.apply_managed_file({"name": "clock.conf", "content": "v=1"})
            second = operations.apply_managed_file({"name": "clock.conf", "content": "v=2"})
        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertNotEqual(first.data["snapshot_id"], second.data["snapshot_id"])
        self.assertTrue((operations.SNAPSHOT_ROOT / first.data["snapshot_id"]).is_file())
        self.assertTrue((operations.SNAPSHOT_ROOT / second.data["snapshot_id"]).is_file())

    def test_rollback_unknown_snapshot(self):
        res = operations.rollback_managed_file({"snapshot_id": "nope.123"})
        self.assertFalse(res.ok)

    def test_rollback_rejects_bad_snapshot_id(self):
        res = operations.rollback_managed_file({"snapshot_id": "../etc/passwd"})
        self.assertFalse(res.ok)

    def test_list_managed_reports_counts(self):
        operations.apply_managed_file({"name": "one.conf", "content": "a"})
        operations.apply_managed_file({"name": "two.conf", "content": "b"})
        res = operations.list_managed_files({})
        self.assertTrue(res.ok)
        self.assertEqual(len(res.data["files"]), 2)
        self.assertEqual(res.data["snapshots"], 2)


class RegistryWiringTest(unittest.TestCase):
    def test_new_tools_registered(self):
        reg = build_registry()
        for name in ["service.start", "service.stop", "file.apply", "file.rollback", "file.list_managed"]:
            self.assertIn(name, reg)

    def test_service_lifecycle_are_medium(self):
        reg = build_registry()
        self.assertEqual(reg["service.start"].risk.value, "MEDIUM")
        self.assertEqual(reg["service.stop"].risk.value, "MEDIUM")
        self.assertEqual(reg["file.apply"].risk.value, "MEDIUM")

    def test_service_stop_returns_inverse_rollback(self):
        reg = build_registry()
        res = reg["service.stop"].handler({"service": "nginx"})
        self.assertEqual(res.data["rollback"]["tool"], "service.start")


if __name__ == "__main__":
    unittest.main()
