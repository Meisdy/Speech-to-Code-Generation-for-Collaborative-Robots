import time
from scipy.spatial.transform import Rotation
from .base_robot_controller import BaseRobotController

GRIPPER_OPEN_WIDTH  = 100.0  # mm
GRIPPER_CLOSE_WIDTH = 0.0    # mm
GRIPPER_FORCE       = 40.0   # N
GRIPPER_TIMEOUT     = 5.0    # s

MAX_JOINT_SPEED  = 3.14      # rad/s  (≈180°/s, near UR limit)
MAX_JOINT_ACCEL  = 3.14      # rad/s²
MAX_LINEAR_SPEED = 0.5       # m/s
MAX_LINEAR_ACCEL = 0.5       # m/s²

DEFAULT_SPEED = 0.5          # fraction 0.0–1.0

DEFAULT_ROBOT_IP = "169.254.70.80"
POSES_FILE = "Backend/poses/ur_poses.jsonl"

class URController(BaseRobotController):

    def __init__(self, robot_ip: str = DEFAULT_ROBOT_IP, poses_file: str = POSES_FILE, gripper_id: int = 0):
        super().__init__(poses_file)
        self.robot_ip   = robot_ip
        self.gripper_id = gripper_id
        self.connected  = False
        self.gripper_state = "unknown"

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    def connect(self) -> dict:
        self.connected = True
        return {"success": True, "message": "Connected (RTDE and gripper disabled)"}

    def disconnect(self) -> dict:
        self.connected = False
        return {"success": True, "message": "Disconnected (RTDE and gripper disabled)"}

    def is_connected(self) -> bool:
        return self.connected

    # ------------------------------------------------------------------ #
    # Motion helpers
    # ------------------------------------------------------------------ #

    def _pose_to_rotvec(self, pose: dict, offset: list = None) -> list:
        """Convert stored pose (pos + quat) to TCP format [x,y,z,rx,ry,rz]."""
        pos    = list(pose["pos"])
        rotvec = Rotation.from_quat(pose["quat"]).as_rotvec().tolist()
        if offset:
            pos[0] += offset[0]
            pos[1] += offset[1]
            pos[2] += offset[2]
        return pos + rotvec

    # ------------------------------------------------------------------ #
    # Motion
    # ------------------------------------------------------------------ #

    def move_joint(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        return {"success": False, "message": "moveJ not implemented (RTDE disabled)"}

    def move_linear(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        return {"success": False, "message": "moveL not implemented (RTDE disabled)"}

    # ------------------------------------------------------------------ #
    # Gripper
    # ------------------------------------------------------------------ #

    def gripper_open(self) -> dict:
        return {"success": False, "message": "Gripper not implemented (RTDE disabled)"}

    def gripper_close(self) -> dict:
        return {"success": False, "message": "Gripper not implemented (RTDE disabled)"}

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def get_current_state(self) -> dict:
        return {
            "success": False,
            "message": "State not available (RTDE disabled)",
            "gripper_state": self.gripper_state,
        }
