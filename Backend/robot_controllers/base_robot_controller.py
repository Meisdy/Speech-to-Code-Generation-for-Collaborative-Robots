import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger("cobot_backend")


class BaseRobotController(ABC):
    """Abstract base class defining common robot controller interface."""

    def __init__(self, poses_file: str):
        self.poses_file: str = poses_file
        self.poses: dict = self._load_poses()
        self._scripts_file: str = poses_file.replace("_poses.jsonl", "_scripts.jsonl")
        self.scripts: dict = self._load_scripts()
        self.connected: bool = False
        self.gripper_state: Optional[str] = None

    def get_pose(self, name: str) -> Optional[dict]:
        """Return named pose dict or None if not found."""
        return self.poses.get(name)

    def save_pose(self, name: str, overwrite: bool = False) -> dict:
        """Save current robot pose under the given name."""
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
        logger.info(f"Saved position '{name}'")
        return {"success": True, "message": f"Pose '{name}' saved"}

    def delete_pose(self, name: str) -> dict:
        """Delete a named pose."""
        if name not in self.poses:
            logger.info(f"Pose '{name}' unknown")
            return {"success": False, "message": f"Pose '{name}' not found"}
        del self.poses[name]
        self._write_poses()
        logger.info(f"Deleted position '{name}'")
        return {"success": True, "message": f"Pose '{name}' deleted"}

    def save_script(self, name: str, commands: list) -> dict:
        """Save a named command sequence for later replay."""
        self.scripts[name] = commands
        self._write_scripts()
        logger.info("Saved script '%s' with %d command(s)", name, len(commands))
        return {"success": True, "message": f"Script '{name}' saved"}

    def get_script(self, name: str) -> Optional[list]:
        """Return the command list for a named script, or None if not found."""
        return self.scripts.get(name)

    def is_ready(self) -> bool:
        """Returns connected status if not overridden by robot controller."""
        return self.connected

    def activate_robot(self) -> dict:
        """Power on and prepare the robot for motion. No-op for controllers that handle this internally."""
        return {"success": True, "message": "Ready"}

    def enable_freedrive(self) -> dict:
        """Enable freedrive mode. Override in controllers that support it."""
        return {"success": False, "message": "Freedrive not implemented for this robot"}

    def disable_freedrive(self) -> dict:
        """Disable freedrive mode. Override in controllers that support it."""
        return {"success": False, "message": "Freedrive not implemented for this robot"}

    @abstractmethod
    def connect(self) -> dict:
        """Establish connection to robot. Returns dict {"success": bool, "message": str}."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to robot."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check connection status."""
        pass

    @abstractmethod
    def move_joint(self, pose: dict, speed: Optional[float] = None, offset: Optional[list] = None) -> dict:
        """Joint-space move. speed: 0.0-1.0, offset: optional [dx, dy, dz] in mm."""
        pass

    @abstractmethod
    def move_linear(self, pose: dict, speed: Optional[float] = None, offset: Optional[list] = None) -> dict:
        """Linear Cartesian move. speed: 0.0-1.0, offset: optional [dx, dy, dz] in mm."""
        pass

    @abstractmethod
    def gripper_open(self) -> dict:
        """Open gripper. Returns dict {"success": bool, "message": str}."""
        pass

    @abstractmethod
    def gripper_close(self) -> dict:
        """Close gripper. Returns dict {"success": bool, "message": str}."""
        pass

    @abstractmethod
    def get_current_pose(self) -> dict:
        """
        Get current robot state.
        Returns: {
            "success": bool,
            "joint_positions": list,
            "pose": [x, y, z, qx, qy, qz, qw],
            "gripper_state": str,
        }
        """
        pass

    def _load_poses(self) -> dict:
        poses = {}
        if not os.path.exists(self.poses_file):
            os.makedirs(os.path.dirname(self.poses_file), exist_ok=True)
            with open(self.poses_file, 'w'):
                pass
            return poses
        with open(self.poses_file, 'r') as f:
            for line in f:
                entry = json.loads(line.strip())
                poses[entry["name"]] = entry
        return poses

    def _write_poses(self) -> None:
        with open(self.poses_file, 'w') as f:
            for entry in self.poses.values():
                f.write(json.dumps(entry) + '\n')

    def _load_scripts(self) -> dict:
        if not os.path.exists(self._scripts_file):
            os.makedirs(os.path.dirname(self._scripts_file), exist_ok=True)
            with open(self._scripts_file, 'w'):
                pass
            return {}
        scripts = {}
        with open(self._scripts_file, 'r') as f:
            for line in f:
                entry = json.loads(line.strip())
                scripts[entry["name"]] = entry["commands"]
        return scripts

    def _write_scripts(self) -> None:
        with open(self._scripts_file, 'w') as f:
            for name, commands in self.scripts.items():
                f.write(json.dumps({"name": name, "commands": commands}) + '\n')