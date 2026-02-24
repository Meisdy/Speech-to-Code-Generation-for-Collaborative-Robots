import time
from scipy.spatial.transform import Rotation

from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface
import onRobot.gripper as onrobot_gripper

from Backend.robot_controllers.base_robot_controller import BaseRobotController


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
        self._rtde_c    = None
        self._rtde_r    = None
        self._gripper   = None

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    def connect(self) -> dict:
        try:
            self._rtde_c  = RTDEControlInterface(self.robot_ip)
            self._rtde_r  = RTDEReceiveInterface(self.robot_ip)
            self._gripper = onrobot_gripper.RG2(self.gripper_id)
            self.connected = True
            return {"success": True, "message": "Connected"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def disconnect(self) -> dict:
        try:
            if self._rtde_c:
                self._rtde_c.stopScript()
                self._rtde_c.disconnect()
            if self._rtde_r:
                self._rtde_r.disconnect()
            self._rtde_c = self._rtde_r = self._gripper = None
            self.connected = False
            return {"success": True, "message": "Disconnected"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def is_connected(self) -> bool:
        if not (self._rtde_c and self._rtde_r):
            return False
        if not (self._rtde_c.isConnected() and self._rtde_r.isConnected()):
            return False
        try:
            self._gripper.rg_get_width()
        except Exception:
            return False
        return True

    # ------------------------------------------------------------------ #
    # Motion helpers
    # ------------------------------------------------------------------ #

    def _pose_to_rotvec(self, pose: dict, offset: list = None) -> list:
        """Convert stored pose (pos + quat) to RTDE TCP format [x,y,z,rx,ry,rz]."""
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
        try:
            spd = (speed or DEFAULT_SPEED) * MAX_JOINT_SPEED
            acc = (speed or DEFAULT_SPEED) * MAX_JOINT_ACCEL
            if offset:
                target = self._pose_to_rotvec(pose, offset)
                self._rtde_c.moveJ_IK(target, spd, acc)
            else:
                self._rtde_c.moveJ(list(pose["joints"]), spd, acc)
            return {"success": True, "message": "moveJ complete"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def move_linear(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        try:
            target = self._pose_to_rotvec(pose, offset)
            spd    = (speed or DEFAULT_SPEED) * MAX_LINEAR_SPEED
            acc    = (speed or DEFAULT_SPEED) * MAX_LINEAR_ACCEL
            self._rtde_c.moveL(target, spd, acc)
            return {"success": True, "message": "moveL complete"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ------------------------------------------------------------------ #
    # Gripper
    # ------------------------------------------------------------------ #

    def _wait_gripper_idle(self):
        deadline = time.time() + GRIPPER_TIMEOUT
        while time.time() < deadline:
            if not self._gripper.rg_get_busy():
                return
            time.sleep(0.05)
        raise TimeoutError("Gripper did not finish within timeout")

    def gripper_open(self) -> dict:
        try:
            self._gripper.rg_grip(GRIPPER_OPEN_WIDTH, GRIPPER_FORCE)
            self._wait_gripper_idle()
            self.gripper_state = "open"
            return {"success": True, "message": "Gripper opened"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def gripper_close(self) -> dict:
        try:
            self._gripper.rg_grip(GRIPPER_CLOSE_WIDTH, GRIPPER_FORCE)
            self._wait_gripper_idle()
            self.gripper_state = "closed"
            return {"success": True, "message": "Gripper closed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def get_current_state(self) -> dict:
        try:
            joints   = self._rtde_r.getActualQ()
            tcp      = self._rtde_r.getActualTCPPose()
            quat     = Rotation.from_rotvec(tcp[3:]).as_quat().tolist()
            return {
                "success":         True,
                "joint_positions": list(joints),
                "pose":            list(tcp[:3]) + quat,
                "gripper_state":   self.gripper_state,
                "gripper_width_mm": self._gripper.rg_get_width(),
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
