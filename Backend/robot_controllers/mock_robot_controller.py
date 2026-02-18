from .base_robot_controller import BaseRobotController
import time


class MockRobotController(BaseRobotController):
    """Mock robot controller for testing without hardware"""

    def __init__(self):
        """Initialize mock robot with default state"""
        self.connected = False
        self.joint_positions = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.current_pose = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.gripper_state = "open"

    def connect(self):
        """Simulate connection"""
        print("Mock: Connecting to robot...")
        time.sleep(0.5)
        self.connected = True
        return {"success": True, "message": "Mock robot connected"}

    def disconnect(self):
        """Simulate disconnection"""
        print("Mock: Disconnecting...")
        time.sleep(0.2)
        self.connected = False
        return {"success": True, "message": "Mock robot disconnected"}

    def move_joint(self, joint_positions, speed=None):
        """Simulate joint movement"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}

        print(f"Mock: Moving to joint positions {joint_positions} at speed {speed}")
        time.sleep(2.0)  # Simulate motion time
        self.joint_positions = list(joint_positions)
        return {
            "success": True,
            "message": f"Mock joint move complete to {joint_positions}"
        }

    def move_linear(self, pose, speed=None):
        """Simulate linear movement"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}

        print(f"Mock: Linear move to pose {pose} at speed {speed}")
        time.sleep(2.5)
        self.current_pose = list(pose)
        return {
            "success": True,
            "message": f"Mock linear move complete to {pose}"
        }

    def move_relative(self, offset):
        """Simulate relative movement"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}

        print(f"Mock: Relative move by offset {offset}")
        time.sleep(1.5)
        # Simulate pose update
        self.current_pose = [p + o for p, o in zip(self.current_pose, offset)]
        return {
            "success": True,
            "message": f"Mock relative move complete by {offset}"
        }

    def gripper_open(self):
        """Simulate gripper opening"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}

        print("Mock: Opening gripper")
        time.sleep(0.5)
        self.gripper_state = "open"
        return {"success": True, "message": "Mock gripper opened"}

    def gripper_close(self, force=None):
        """Simulate gripper closing"""
        if not self.connected:
            return {"success": False, "message": "Robot not connected"}

        print(f"Mock: Closing gripper with force {force}")
        time.sleep(0.5)
        self.gripper_state = "closed"
        return {"success": True, "message": f"Mock gripper closed (force={force})"}

    def get_current_state(self):
        """Return current mock state"""
        return {
            "success": True,
            "joint_positions": self.joint_positions,
            "pose": self.current_pose,
            "gripper_state": self.gripper_state,
            "connected": self.connected
        }

    def is_connected(self):
        """Check connection status"""
        return self.connected
