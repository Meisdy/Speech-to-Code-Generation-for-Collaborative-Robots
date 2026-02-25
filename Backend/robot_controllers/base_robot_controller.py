from abc import ABC, abstractmethod
import os, json
from typing import Optional


class BaseRobotController(ABC):
    """Abstract base class defining common robot controller interface"""

    def __init__(self, poses_file: str):
        self.poses_file = poses_file
        self.poses = self._load_poses()
        self.connected : bool = False
        self.gripper_state : str = 'open'
        self.joint_angles : list | None = None
        self.positions = None


    # --- Pose management (concrete, shared) ---
    def _load_poses(self) -> dict:
        poses = {}
        if not os.path.exists(self.poses_file):
            os.makedirs(os.path.dirname(self.poses_file), exist_ok=True)
            open(self.poses_file, 'w').close()
            return poses
        with open(self.poses_file, 'r') as f:
            for line in f:
                entry = json.loads(line.strip())
                poses[entry["name"]] = entry
        return poses

    def get_pose(self, name: str) -> Optional[dict]:
        return self.poses.get(name)

    def save_pose(self, name: str, overwrite: bool = False) -> dict:
        if name in self.poses and not overwrite:
            return {"success": False, "message": f"Pose '{name}' already exists"}
        state = self.get_current_pose()
        if not state.get("success"):
            return {"success": False, "message": f"Could not read robot state: {state.get('message', 'unknown error')}"}
        entry = {
            "name": name,
            "pos": state["pose"][:3],
            "quat": state["pose"][3:],
            "joints": state["joint_positions"]
        }
        self.poses[name] = entry
        self._write_poses()
        return {"success": True, "message": f"Pose '{name}' saved"}

    def delete_pose(self, name: str) -> dict:
        if name not in self.poses:
            return {"success": False, "message": f"Pose '{name}' not found"}
        del self.poses[name]
        self._write_poses()
        return {"success": True, "message": f"Pose '{name}' deleted"}

    def _write_poses(self):
        with open(self.poses_file, 'w') as f:
            for entry in self.poses.values():
                f.write(json.dumps(entry) + '\n')

    # --- Abstract movement commands ---

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
    def is_connected(self):
        """
        Check connection status
        Returns: bool
        """
        pass


    @abstractmethod
    def move_joint(self, pose: dict, speed=None, offset: list = None) -> dict:
        """
        Args:
            pose: full pose dict
            speed: optional (0.0-1.0)
            offset: optional [dx, dy, dz] applied to pos before moving
        """
        pass

    @abstractmethod
    def move_linear(self, pose: dict, speed=None, offset: list = None) -> dict:
        """
        Args:
            pose: full pose dict
            speed: optional (0.0-1.0)
            offset: optional [dx, dy, dz] applied to pos before moving
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
    def gripper_close(self):
        """
        Close gripper
        Returns: dict {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def get_current_pose(self):
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
