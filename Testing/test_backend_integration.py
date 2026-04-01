"""
Backend Integration Test — tests the full ZeroMQ request/response path.

Prerequisites:
    - Backend must be running: python -m Backend.main
    - No hardware required — all tests target the Mock adapter

Run:
    python -m pytest Testing/test_backend_integration.py -v
"""

import unittest
from Frontend.communication_client import ClientZeroMQ

ROBOT   = "mock"
ADDRESS = "tcp://localhost:5555"


class TestBackendIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = ClientZeroMQ(ADDRESS)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    # ── Utility commands ───────────────────────────────────────────────────────

    def test_01_ping(self) -> None:
        success, resp = self.client.send_command("ping", {})
        self.assertTrue(success)
        self.assertEqual(resp["command"], "success")
        self.assertEqual(resp["data"]["message"], "Backend Alive")

    def test_02_get_status(self) -> None:
        success, resp = self.client.send_command("get_status", {})
        self.assertTrue(success)
        self.assertEqual(resp["command"], "success")
        self.assertIn("Connected Robots", resp["data"])

    def test_03_unknown_command(self) -> None:
        success, resp = self.client.send_command("launch_rockets", {})
        self.assertTrue(success)
        self.assertEqual(resp["command"], "rejected")

    # ── Rejection cases ────────────────────────────────────────────────────────

    def test_04_unknown_robot_type(self) -> None:
        success, resp = self.client.send_command("execute_sequence", {
            "robot": "r2d2",
            "commands": [{"action": "gripper", "command": "open"}]
        })
        self.assertTrue(success)
        self.assertEqual(resp["command"], "rejected")

    def test_05_empty_commands(self) -> None:
        success, resp = self.client.send_command("execute_sequence", {
            "robot": ROBOT,
            "commands": []
        })
        self.assertTrue(success)
        self.assertEqual(resp["command"], "success")  # Empty sequence completes trivially

    def test_06_unknown_pose(self) -> None:
        success, resp = self.client.send_command("execute_sequence", {
            "robot": ROBOT,
            "commands": [{
                "action": "move",
                "motion_type": "moveJ",
                "target": {"type": "named_pose", "name": "this_pose_does_not_exist"}
            }]
        })
        self.assertTrue(success)
        self.assertEqual(resp["command"], "rejected")

    # ── Happy path — individual actions ───────────────────────────────────────

    def _execute(self, commands: list) -> dict:
        """Helper — fire a sequence and return the response."""
        success, resp = self.client.send_command("execute_sequence", {
            "robot": ROBOT,
            "commands": commands
        })
        self.assertTrue(success, "ZeroMQ send failed")
        return resp

    def test_07_move_joint(self) -> None:
        resp = self._execute([{
            "action": "move",
            "motion_type": "moveJ",
            "target": {"type": "named_pose", "name": "home"}
        }])
        self.assertEqual(resp["command"], "success")

    def test_08_move_joint_offset(self) -> None:
        resp = self._execute([{
            "action": "move",
            "motion_type": "moveJ",
            "target": {"type": "offset_from_pose", "name": "home",
                       "offset": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 100.0}}
        }])
        self.assertEqual(resp["command"], "success")

    def test_09_move_linear(self) -> None:
        resp = self._execute([{
            "action": "move",
            "motion_type": "moveL",
            "target": {"type": "named_pose", "name": "home"}
        }])
        self.assertEqual(resp["command"], "success")

    def test_10_move_linear_offset(self) -> None:
        resp = self._execute([{
            "action": "move",
            "motion_type": "moveL",
            "target": {"type": "offset_from_pose", "name": "home",
                       "offset": {"x_mm": 0.0, "y_mm": 0.0, "z_mm": 100.0}}
        }])
        self.assertEqual(resp["command"], "success")

    def test_11_gripper_open(self) -> None:
        resp = self._execute([{"action": "gripper", "command": "open"}])
        self.assertEqual(resp["command"], "success")

    def test_12_gripper_close(self) -> None:
        resp = self._execute([{"action": "gripper", "command": "close"}])
        self.assertEqual(resp["command"], "success")

    def test_13_wait(self) -> None:
        resp = self._execute([{"action": "wait", "duration_s": 0.1}])
        self.assertEqual(resp["command"], "success")

    def test_14_pose_teach_and_delete(self) -> None:
        resp = self._execute([{
            "action": "pose",
            "command": "teach",
            "pose_name": "_integration_test_pose",
            "overwrite": True
        }])
        self.assertEqual(resp["command"], "success")

        resp = self._execute([{
            "action": "pose",
            "command": "delete",
            "pose_name": "_integration_test_pose"
        }])
        self.assertEqual(resp["command"], "success")

    def test_15_freedrive(self) -> None:
        resp = self._execute([{"action": "freedrive", "active": True}])
        self.assertIn(resp["command"], ("success", "error"))  # May not be supported — must not crash

        resp = self._execute([{"action": "freedrive", "active": False}])
        self.assertIn(resp["command"], ("success", "error"))

    def test_16_connection_disconnect_reconnect(self) -> None:
        resp = self._execute([{"action": "connection", "command": "disconnect"}])
        self.assertEqual(resp["command"], "success")

        resp = self._execute([{"action": "connection", "command": "connect"}])
        self.assertEqual(resp["command"], "success")

    # ── Multi-command sequence ─────────────────────────────────────────────────

    def test_17_full_sequence(self) -> None:
        resp = self._execute([
            {"action": "move", "motion_type": "moveJ",
             "target": {"type": "named_pose", "name": "home"}},
            {"action": "gripper", "command": "open"},
            {"action": "wait", "duration_s": 0.1},
            {"action": "gripper", "command": "close"},
            {"action": "move", "motion_type": "moveJ",
             "target": {"type": "named_pose", "name": "home"}},
        ])
        self.assertEqual(resp["command"], "success")
        self.assertIn("5", resp["data"]["message"])  # "Sequence of 5 command(s) completed"


if __name__ == "__main__":
    unittest.main()