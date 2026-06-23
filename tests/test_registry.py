import unittest

from safeops_agent.tools.registry import build_registry


class RegistryTest(unittest.TestCase):
    def test_new_readonly_tools_are_registered(self):
        tools = build_registry()

        expected = {
            "network.connections",
            "network.listening_ports",
            "disk.partitions",
            "user.list",
            "schedule.cron",
            "environment.safe",
            "package.query",
        }
        self.assertTrue(expected.issubset(set(tools)))

    def test_tools_have_categories(self):
        for tool in build_registry().values():
            self.assertTrue(tool.category)


if __name__ == "__main__":
    unittest.main()
