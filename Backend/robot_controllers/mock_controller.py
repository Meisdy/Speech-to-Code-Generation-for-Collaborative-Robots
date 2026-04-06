import logging
import time
from typing import Optional

from Backend.robot_controllers.base_robot_controller import BaseRobotController

logger = logging.getLogger("cobot_backend")


class MockRobotController(BaseRobotController):
    """Mock robot controller for testing without hardware."""

    def __init__(self, poses_file: str = "Backend/poses/mock_poses.jsonl") -> None:
        super().__init__(poses_file)
        self._joint_angles: list = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._tcp_pose: list = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]  # pos + identity quat

    def connect(self) -> dict:
        """Simulate connection delay and mark robot as connected."""
        time.sleep(0.5)
        self.connected = True
        logger.info("Connected")
        return {"success": True, "message": "Mock robot connected"}

    def disconnect(self) -> None:
        """Simulate disconnect delay and mark robot as disconnected."""
        time.sleep(0.2)
        self.connected = False
        logger.info("Disconnected")

    def is_connected(self) -> bool:
        """Return current connection state."""
        return self.connected

    def move_joint(self, pose: dict, speed: Optional[float] = None, offset: Optional[list] = None) -> dict:  # speed ignored in mock
        """Simulate a joint-space move."""
        logger.info("Moving with moveJ to '%s'", pose["name"])
        target_pos = list(pose["pos"])
        if offset:
            target_pos = [p + o for p, o in zip(target_pos, offset)]
            logger.info("Offset used: '%s'", offset)
        time.sleep(2)
        self._joint_angles = list(pose["joints"])
        self._tcp_pose = target_pos + list(pose["quat"])
        return {"success": True, "message": f"Mock moveJ complete to '{pose['name']}'"}

    def move_linear(self, pose: dict, speed: Optional[float] = None, offset: Optional[list] = None) -> dict:  # speed ignored in mock
        """Simulate a linear Cartesian move."""
        logger.info("Moving with moveL to '%s'", pose["name"])
        target_pos = list(pose["pos"])
        if offset:
            target_pos = [p + o for p, o in zip(target_pos, offset)]
            logger.info("Offset used: '%s'", offset)
        time.sleep(2)
        self._joint_angles = list(pose["joints"])
        self._tcp_pose = target_pos + list(pose["quat"])
        return {"success": True, "message": f"Mock moveL complete to '{pose['name']}'"}

    def gripper_open(self) -> dict:
        """Simulate gripper open."""
        logger.info("Opening gripper")
        time.sleep(0.5)
        self.gripper_state = "open"
        return {"success": True, "message": "Mock gripper opened"}

    def gripper_close(self) -> dict:
        """Simulate gripper close."""
        logger.info("Closing gripper")
        time.sleep(0.5)
        self.gripper_state = "closed"
        return {"success": True, "message": "Mock gripper closed"}

    def get_current_pose(self) -> dict:
        """Return current simulated robot state."""
        return {
            "success":         True,
            "joint_positions": self._joint_angles,
            "pose":            self._tcp_pose,
            "gripper_state":   self.gripper_state,
        }

    def enable_freedrive(self) -> dict:
        logger.info("freedrive enabled")
        return {"success": True, "message": "Freedrive enabled"}

    def disable_freedrive(self) -> dict:
        logger.info("freedrive disabled")
        return {"success": True, "message": "Freedrive disabled"}