import unittest
from communication_client import ClientZeroMQ
import time

class TestBackendLive(unittest.TestCase):
    ROBOT_TYPE = "mock"  # Choose the robot type here

    @classmethod
    def setUpClass(cls):
        cls.client = ClientZeroMQ("tcp://localhost:5555")
        time.sleep(2)  # Backend startup

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_ping(self):
        success, resp = self.client.send_command("ping", {})
        self.assertTrue(success)
        self.assertEqual(resp["data"]["message"], "Backend Alive")

    def test_unknown_command(self):
        success, resp = self.client.send_command("invalid", {})
        self.assertTrue(success)
        self.assertEqual(resp["command"], "rejected")

    def test_get_status(self):
        success, resp = self.client.send_command("get_status", {})
        self.assertTrue(success)
        self.assertEqual(resp["command"], "success")

    def test_execute_move_J_mock(self):
        data = {
            "robot": self.ROBOT_TYPE,
            "commands": [{
                "action": "move",
                "motion_type": "moveJ",
                "target": {"name": "home"},
                "speed": 0.5
            }]
        }
        success, resp = self.client.send_command("execute_sequence", data)
        self.assertTrue(success)
        self.assertEqual(resp["command"], "success")

    def test_execute_move_L_mock(self):
        data = {
            "robot": self.ROBOT_TYPE,
            "commands": [{
                "action": "move",
                "motion_type": "moveL",
                "target": {"name": "home"},
                "speed": 0.5
            }]
        }
        success, resp = self.client.send_command("execute_sequence", data)
        self.assertTrue(success)
        self.assertEqual(resp["command"], "success")

    def test_execute_gripper_sequence(self):
        data = {
            "robot": self.ROBOT_TYPE,
            "commands": [
                {"action": "gripper", "command": "open"},
                {"action": "wait", "duration_s": 0.1},  # Backend handles ✓
                {"action": "gripper", "command": "close"}
            ]
        }
        success, resp = self.client.send_command("execute_sequence", data)
        self.assertTrue(success)

        responses = resp["data"]["responses"]
        print("Responses:", responses)  # PyCharm console debug

        self.assertEqual(len(responses), 3)

        # Wait returns dict without "success" key → use .get()
        success_flags = [r.get("success", True) for r in responses]  # Default True for wait
        self.assertTrue(all(success_flags))

    def test_teach_pose(self):
        data = {
            "robot": self.ROBOT_TYPE,
            "commands": [{
                "action": "pose",
                "command": "teach",
                "pose_name": "test_pose",
                "overwrite": True
            }]
        }
        success, resp = self.client.send_command("execute_sequence", data)
        self.assertTrue(success)

    def test_delete_pose(self):
        data = {
            "robot": self.ROBOT_TYPE,
            "commands": [{
                "action": "pose",
                "command": "delete",
                "pose_name": "test_pose"
            }]
        }
        success, resp = self.client.send_command("execute_sequence", data)
        self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()
