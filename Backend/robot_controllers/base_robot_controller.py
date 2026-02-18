from abc import ABC, abstractmethod


class BaseRobotController(ABC):
    """Abstract base class defining common robot controller interface"""

    @abstractmethod
    def connect(self):
        """
        Establish connection to robot
        Returns: dict {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Close connection to robot
        Returns: dict {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def move_joint(self, joint_positions, speed=None):
        """
        Move to absolute joint positions
        Args:
            joint_positions: list/array of joint angles
            speed: optional speed parameter (0.0-1.0 normalized or vendor-specific)
        Returns: dict {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def move_linear(self, pose, speed=None):
        """
        Linear Cartesian movement to pose
        Args:
            pose: target pose [x, y, z, rx, ry, rz] or transformation matrix
            speed: optional speed parameter
        Returns: dict {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def move_relative(self, offset):
        """
        Move relative to current position
        Args:
            offset: relative displacement [dx, dy, dz, drx, dry, drz]
        Returns: dict {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def gripper_open(self):
        """
        Open gripper
        Returns: dict {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def gripper_close(self, force=None):
        """
        Close gripper
        Args:
            force: optional gripper force parameter
        Returns: dict {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def get_current_state(self):
        """
        Get current robot state
        Returns: dict {
            "success": bool,
            "joint_positions": list,
            "pose": list,
            "gripper_state": str,
            ...additional vendor-specific data
        }
        """
        pass

    @abstractmethod
    def is_connected(self):
        """
        Check connection status
        Returns: bool
        """
        pass
