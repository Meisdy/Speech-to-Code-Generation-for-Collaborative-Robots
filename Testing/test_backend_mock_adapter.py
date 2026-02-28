import unittest
from Backend.robot_controllers.mock_controller import MockRobotController

class TestMockRobotController(unittest.TestCase):
    def setUp(self):
        self.mock_robot = MockRobotController()

    def test_connect(self):
        response = self.mock_robot.connect()
        self.assertTrue(response["success"])
        self.assertTrue(self.mock_robot.is_connected())

    def test_disconnect(self):
        self.mock_robot.connect()  # Ensure connected
        response = self.mock_robot.disconnect()
        self.assertTrue(response["success"])
        self.assertFalse(self.mock_robot.is_connected())

    def test_move_joint_home(self):
        pose = {"name": "home", "pos": [0.0]*3, "quat": [1.0, 0.0, 0.0, 0.0], "joints": [0.0]*6}
        response = self.mock_robot.move_joint(pose, speed=0.5)
        self.assertTrue(response["success"])
        self.assertEqual(response["message"], "Mock MoveJ complete to 'home'")

    def test_move_joint_offset(self):
        pose = {"name": "home", "pos": [0.1, 0.2, 0.3], "quat": [1.0, 0.0, 0.0, 0.0], "joints": [0.0]*6}
        response = self.mock_robot.move_joint(pose, speed=0.5, offset=[0.01, 0.02, 0.03])
        self.assertTrue(response["success"])

    def test_move_linear(self):
        pose = {"name": "pick", "pos": [0.5, 0.0, 0.3], "quat": [1.0, 0.0, 0.0, 0.0], "joints": [0.0]*6}
        response = self.mock_robot.move_linear(pose, speed=0.3)
        self.assertTrue(response["success"])
        self.assertIn("MoveL complete to 'pick'", response["message"])

    def test_gripper_open(self):
        response = self.mock_robot.gripper_open()
        self.assertEqual(response, {"success": True, "message": "Mock gripper opened"})
        self.assertEqual(self.mock_robot.gripper_state, "open")

    def test_gripper_close(self):
        response = self.mock_robot.gripper_close()
        self.assertEqual(response, {"success": True, "message": "Mock gripper closed"})
        self.assertEqual(self.mock_robot.gripper_state, "closed")

    def test_get_current_pose(self):
        self.mock_robot.connect()
        response = self.mock_robot.get_current_pose()
        self.assertTrue(response["success"])
        self.assertIn("joint_positions", response)
        self.assertIn("pose", response)
        self.assertIn("gripper_state", response)

if __name__ == '__main__':
    unittest.main()
