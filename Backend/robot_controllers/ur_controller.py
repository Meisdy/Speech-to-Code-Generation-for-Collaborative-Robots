from .base_robot_controller import BaseRobotController


class URController(BaseRobotController):
    def __init__(self, poses_file: str ):
        super().__init__(poses_file)
        self.joint_angles = None
        self.positions = None

    def connect(self):
        """
        Establish connection to robot
        Returns: dict {"success": bool, "message": str}
        """
        pass

    def disconnect(self):
        """
        Close connection to robot
        Returns: dict {"success": bool, "message": str}
        """
        pass

    def is_connected(self):
        """
        Check connection status
        Returns: bool
        """
        pass

    def move_joint(self, pose: dict, speed=None, offset: list = None) -> dict:
        """
        Args:
            pose: full pose dict
            speed: optional (0.0-1.0)
            offset: optional [dx, dy, dz] applied to pos before moving
        """
        pass

    def move_linear(self, pose: dict, speed=None, offset: list = None) -> dict:
        """
        Args:
            pose: full pose dict
            speed: optional (0.0-1.0)
            offset: optional [dx, dy, dz] applied to pos before moving
        """
        pass

    def gripper_open(self):
        """
        Open gripper
        Returns: dict {"success": bool, "message": str}
        """
        pass

    def gripper_close(self):
        """
        Close gripper
        Returns: dict {"success": bool, "message": str}
        """
        pass

    def get_current_state(self):
        """
        Get current robot state
        Returns: dict {
            "success": bool,
            "joint_positions": list,
            "pose": [x, y, z, qx, qy, qz, qw],  # pos (3) + quaternion (4)
            "gripper_state": str,
            ...additional vendor-specific data
        }
        """
        pass