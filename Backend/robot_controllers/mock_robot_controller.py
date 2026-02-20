from .base_robot_controller import BaseRobotController
import time


class MockRobotController(BaseRobotController):
    """Mock robot controller for testing without hardware"""

    def __init__(self, poses_file: str = "Backend/poses/mock_poses.jsonl"):
        super().__init__(poses_file)
        self.joint_angles = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.positions = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]  # pos + identity quat

    def connect(self):
        print("Mock: Connecting to robot...")
        time.sleep(0.5)
        self.connected = True
        return {"success": True, "message": "Mock robot connected"}

    def disconnect(self):
        print("Mock: Disconnecting...")
        time.sleep(0.2)
        self.connected = False
        return {"success": True, "message": "Mock robot disconnected"}

    def is_connected(self):
        return self.connected

    def move_joint(self, pose: dict, speed=None, offset: list = None):
        target_pos = list(pose["pos"])
        if offset:
            target_pos = [p + o for p, o in zip(target_pos, offset)]

        print(f"Mock: MoveJ to '{pose['name']}' offset={offset} speed={speed}")
        time.sleep(2)
        self.joint_angles = list(pose["joints"])
        self.positions = target_pos + list(pose["quat"])
        return {"success": True, "message": f"Mock MoveJ complete to '{pose['name']}'"}

    def move_linear(self, pose: dict, speed=None, offset: list = None):
        target_pos = list(pose["pos"])
        if offset:
            target_pos = [p + o for p, o in zip(target_pos, offset)]

        print(f"Mock: MoveL to '{pose['name']}' offset={offset} speed={speed}")
        time.sleep(2)
        self.positions = target_pos + list(pose["quat"])
        return {"success": True, "message": f"Mock MoveL complete to '{pose['name']}'"}

    def gripper_open(self):
        print("Mock: Opening gripper")
        time.sleep(0.5)
        self.gripper_state = "open"
        return {"success": True, "message": "Mock gripper opened"}

    def gripper_close(self):
        print("Mock: Closing gripper")
        time.sleep(0.5)
        self.gripper_state = "closed"
        return {"success": True, "message": "Mock gripper closed"}

    def get_current_state(self):
        return {
            "success": True,
            "joint_positions": self.joint_angles,
            "pose": self.positions,  # [x, y, z, qx, qy, qz, qw]
            "gripper_state": self.gripper_state,
            "connected": self.connected
        }
