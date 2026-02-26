"""
URController — pure TCP/IP socket implementation for UR10 (and compatible UR cobots).

Port layout
-----------
  29999  Dashboard Server  : text-based admin commands (power, brake release, play/stop)
  30002  Secondary Client  : URScript commands sent here (fire-and-forget per command)
  30003  Real-Time Client  : 125 Hz binary state stream — joints and TCP pose

State packet (port 30003, CB3 / e-Series)
------------------------------------------
  Packets are 1060 bytes (CB3) or 1220 bytes (e-Series), big-endian doubles.
  Offsets used:
      252  actual joint positions  q[0..5]   (6 × double, rad)
      444  actual TCP pose         [x,y,z,rx,ry,rz]  (6 × double, rotvec, metres)
  Reference: UR Client Interface documentation v3 / v5.

Gripper
-------
  Open/close is handled by loading and executing locally saved URP programs
  on the robot via the Dashboard Server.
"""
import socket
import struct
import time
import logging
from scipy.spatial.transform import Rotation
from Backend.robot_controllers.base_robot_controller import BaseRobotController

logger = logging.getLogger("cobot_backend")

# ── Module-level constants ─────────────────────────────────────────────────────

DEFAULT_ROBOT_IP = "192.168.1.100"
POSES_FILE       = "Backend/poses/ur_poses.jsonl"

DASHBOARD_PORT   = 29999
SCRIPT_PORT      = 30002
STATE_PORT       = 30003

SOCKET_TIMEOUT   = 5.0    # seconds
STATE_RECV_BYTES = 1220   # max packet size; covers both CB3 (1060) and e-Series (1220)

RT_JOINT_OFFSET  = 252    # byte offset of joint positions in state packet
RT_TCP_OFFSET    = 444    # byte offset of TCP pose in state packet

MAX_JOINT_SPEED  = 3.14   # rad/s
MAX_JOINT_ACCEL  = 3.14   # rad/s²
MAX_LINEAR_SPEED = 0.5    # m/s
MAX_LINEAR_ACCEL = 0.5    # m/s²
DEFAULT_SPEED    = 0.5    # fraction 0.0–1.0


# ── Module-level helpers ───────────────────────────────────────────────────────

def _recv_exactly(sock: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes from *sock*, blocking until all bytes arrive."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed before reading expected bytes")
        buf += chunk
    return buf


# ── Controller ────────────────────────────────────────────────────────────────

class URController(BaseRobotController):
    """
    UR10 controller using raw TCP sockets.

    Socket strategy:
      - _dash_sock      : persistent connection to Dashboard Server (29999)
      - _freedrive_sock : persistent connection kept open while freedrive is active
      - Script port (30002) : short-lived connection opened per motion command
      - State port (30003)  : short-lived connection opened per state read
    """

    # ── Tuning constants ──────────────────────────────────────────────────────

    MOTION_TIMEOUT       = 30.0   # seconds before giving up on a motion
    MOTION_POLL_INTERVAL = 0.1    # seconds between joint position polls
    MOTION_THRESHOLD     = 0.001  # rad — max delta to consider joints stopped
    MOTION_START_DELAY   = 0.3    # seconds to wait for motion to begin before polling
    ACTIVATION_SETTLE    = 3.8    # seconds to wait after RUNNING confirmed — the Dashboard
                                  # sends an implicit stop ~3.5s after brake release if no
                                  # program is running; this clears that window

    GRIPPER_OPEN_PROGRAM  = "open_UG2_Gripper.urp"
    GRIPPER_CLOSE_PROGRAM = "close_UG2_Gripper.urp"
    GRIPPER_ACTUATE_TIME  = 4.0   # seconds — tune to match physical actuation duration

    # ── Initialisation ────────────────────────────────────────────────────────

    def __init__(self, robot_ip: str = DEFAULT_ROBOT_IP, poses_file: str = POSES_FILE):
        super().__init__(poses_file)
        self.robot_ip        = robot_ip
        self._dash_sock      : socket.socket | None = None
        self._freedrive_sock : socket.socket | None = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> dict:
        try:
            self._dash_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._dash_sock.settimeout(SOCKET_TIMEOUT)
            self._dash_sock.connect((self.robot_ip, DASHBOARD_PORT))
            self._dash_sock.recv(1024)  # discard welcome banner
            self.connected = True
            logger.info("Connected")
            return {"success": True, "message": "Connected"}
        except OSError as e:
            return {"success": False, "safe": False, "status": "UNKNOWN", "message": e}
        except Exception as e:
            self._close_sockets()
            logger.exception("Connection failed")
            return {"success": False, "message": str(e)}

    def disconnect(self) -> None:
        try:
            self._close_sockets()
            self.connected = False
            logger.info("Disconnected")
        except Exception:
            logger.warning("Error during disconnect", exc_info=True)

    def is_connected(self) -> bool:
        if not self.connected:
            return False
        try:
            mode = self.get_robot_mode()
            return mode["success"] and mode["mode"] not in ("DISCONNECTED", "UNKNOWN")

        except Exception:
            logger.exception("is_connected check failed")
            return False

    def is_ready(self) -> bool:
        if not self.connected:
            return False
        safety = self.get_safety_status()
        if not self.connected:  # socket may have died during the call above
            return False
        mode = self.get_robot_mode()
        return safety.get("safe") and mode.get("ready")

    def get_safety_status(self) -> dict:
        """Query the robot's current safety status."""
        try:
            reply = self._dashboard_cmd("safetystatus").upper()

            if "ROBOT_EMERGENCY_STOP" in reply or "SYSTEM_EMERGENCY_STOP" in reply:
                return {"success": True, "safe": False, "status": "EMERGENCY_STOP",
                        "message": "E-stop is active — release the e-stop and try again"}
            if "SAFEGUARD_STOP" in reply:
                return {"success": True, "safe": False, "status": "SAFEGUARD_STOP",
                        "message": "Safeguard stop is active — check external safety inputs"}
            if "PROTECTIVE_STOP" in reply or "RECOVERY" in reply:
                return {"success": True, "safe": False, "status": "PROTECTIVE_STOP",
                        "message": "Protective stop active — clear the stop on the pendant"}
            if "VIOLATION" in reply or "FAULT" in reply:
                return {"success": True, "safe": False, "status": "FAULT",
                        "message": f"Robot fault: {reply}"}
            if "REDUCED" in reply:
                return {"success": True, "safe": True, "status": "REDUCED",
                        "message": "Operating in reduced mode"}
            if "NORMAL" in reply:
                return {"success": True, "safe": True, "status": "NORMAL",
                        "message": ""}

            return {"success": True, "safe": False, "status": "UNKNOWN",
                    "message": f"Unrecognised safety status: {reply}"}
        except OSError as e:
            return {"success": False, "safe": False, "status": "UNKNOWN", "message": {e}}
        except Exception as e:
            logger.exception("Failed to get safety status")
            return {"success": False, "safe": False, "status": "UNKNOWN", "message": str(e)}

    def get_robot_mode(self) -> dict:
        """Query the robot's current operational mode."""
        try:
            reply = self._dashboard_cmd("robotmode").upper()

            if "RUNNING" in reply:
                return {"success": True, "mode": "RUNNING", "ready": True,
                        "message": "Robot is active and ready"}
            if "IDLE" in reply:
                return {"success": True, "mode": "IDLE", "ready": False,
                        "message": "Robot is powered on but brakes are engaged"}
            if "POWER_OFF" in reply:
                return {"success": True, "mode": "POWER_OFF", "ready": False,
                        "message": "Robot is powered off"}
            if "NO_CONTROLLER" in reply or "DISCONNECTED" in reply:
                return {"success": True, "mode": "DISCONNECTED", "ready": False,
                        "message": "Robot controller is not ready"}

            return {"success": True, "mode": "UNKNOWN", "ready": False,
                    "message": f"Unrecognised robot mode: {reply}"}
        except OSError as e:
            return {"success": False, "safe": False, "status": "UNKNOWN", "message": {e}}
        except Exception as e:
            logger.exception("Failed to get robot mode")
            return {"success": False, "mode": "UNKNOWN", "ready": False, "message": str(e)}

    def activate_robot(self) -> dict:
        """
        Power on the robot and release brakes, ready for motion commands.
        Checks safety status and robot mode before attempting activation.
        """
        try:
            logger.info("Activating Robot")
            safety = self.get_safety_status()
            if not safety["success"] or not safety["safe"]:
                return {"success": False, "message": safety["message"]}

            mode = self.get_robot_mode()
            if not mode["success"]:
                return {"success": False, "message": mode["message"]}
            if mode["ready"]:
                return {"success": True, "message": "Robot is already active"}
            if mode["mode"] == "DISCONNECTED":
                return {"success": False, "message": mode["message"]}

            if mode["mode"] == "POWER_OFF":
                self._dashboard_cmd("power on")
                deadline = time.time() + 15.0
                while time.time() < deadline:
                    if self.get_robot_mode()["mode"] == "IDLE":
                        break
                    time.sleep(0.5)
                else:
                    return {"success": False, "message": "Timed out waiting for robot to power on"}

            self._dashboard_cmd("brake release")
            deadline = time.time() + 15.0
            while time.time() < deadline:
                if self.get_robot_mode()["ready"]:
                    time.sleep(self.ACTIVATION_SETTLE)  # Dashboard sends implicit stop ~3s after brake release
                    logger.info("Robot active and ready")
                    return {"success": True, "message": "Robot active and ready"}
                time.sleep(0.5)

            # Re-check safety — e-stop may have been triggered during activation
            safety = self.get_safety_status()
            if not safety["safe"]:
                return {"success": False, "message": safety["message"]}
            return {"success": False, "message": "Timed out waiting for brakes to release"}

        except Exception as e:
            logger.exception("Robot activation failed")
            return {"success": False, "message": str(e)}

    def _close_sockets(self):
        for attr in ("_dash_sock", "_freedrive_sock"):
            sock = getattr(self, attr, None)
            if sock:
                try:
                    sock.close()
                except Exception:
                    logger.warning("Error closing socket '%s'", attr, exc_info=True)
            setattr(self, attr, None)

    # ── Internal communication ────────────────────────────────────────────────

    def _dashboard_cmd(self, cmd: str) -> str:
        if self._dash_sock is None:
            raise ConnectionError("Not connected")
        try:
            self._dash_sock.sendall((cmd + "\n").encode("utf-8"))
            return self._dash_sock.recv(1024).decode("utf-8").strip()
        except OSError:
            self._close_sockets()
            self.connected = False
            logger.warning("Connection lost")  # logged once here, callers don't re-log
            raise

    def _send_script(self, script: str):
        """Send a URScript command to port 30002 over a short-lived connection."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(SOCKET_TIMEOUT)
            s.connect((self.robot_ip, SCRIPT_PORT))
            if not script.endswith("\n"):
                script += "\n"
            s.sendall(script.encode("utf-8"))
            time.sleep(0.05)  # brief pause before closing so the robot starts receiving

    # ── Motion ────────────────────────────────────────────────────────────────

    @staticmethod
    def _pose_to_rotvec(pose: dict, offset: list = None) -> list:
        pos = list(pose["pos"])
        rotvec = Rotation.from_quat(pose["quat"]).as_rotvec().tolist()
        if offset:
            pos[0] += offset[0] / 1000.0
            pos[1] += offset[1] / 1000.0
            pos[2] += offset[2] / 1000.0
        return pos + rotvec

    def _wait_motion_complete(self) -> dict:
        """
        Block until the robot stops moving.
        Polls joint positions and returns once all joints move less than
        MOTION_THRESHOLD rad between consecutive reads.
        """
        time.sleep(self.MOTION_START_DELAY)
        deadline    = time.time() + self.MOTION_TIMEOUT
        prev_joints = None

        while time.time() < deadline:
            state = self.get_current_pose()
            if not state["success"]:
                return {"success": False, "message": f"Pose read failed during motion: {state['message']}"}
            curr_joints = state["joint_positions"]
            if prev_joints is not None:
                deltas = [abs(c - p) for c, p in zip(curr_joints, prev_joints)]
                if all(d < self.MOTION_THRESHOLD for d in deltas):
                    return {"success": True, "message": "Motion complete"}
            prev_joints = curr_joints
            time.sleep(self.MOTION_POLL_INTERVAL)

        return {"success": False, "message": f"Motion did not complete within {self.MOTION_TIMEOUT}s"}

    def move_joint(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        """
        Joint-space move (moveJ). Blocks until motion is complete.
        If an offset is provided, the robot performs IK internally via a pose target.
        """
        try:
            logger.info("Moving with moveJ to '%s'", pose["name"])
            spd = (speed or DEFAULT_SPEED) * MAX_JOINT_SPEED
            acc = (speed or DEFAULT_SPEED) * MAX_JOINT_ACCEL

            if offset:
                t = self._pose_to_rotvec(pose, offset)
                script = (
                    f"movej(p[{t[0]:.6f},{t[1]:.6f},{t[2]:.6f},"
                    f"{t[3]:.6f},{t[4]:.6f},{t[5]:.6f}],a={acc:.4f},v={spd:.4f})"
                )
            else:
                j = pose["joints"]
                script = (
                    f"movej([{j[0]:.6f},{j[1]:.6f},{j[2]:.6f},"
                    f"{j[3]:.6f},{j[4]:.6f},{j[5]:.6f}],a={acc:.4f},v={spd:.4f})"
                )

            self._send_script(script)
            return self._wait_motion_complete()
        except Exception as e:
            logger.exception("moveJ failed")
            return {"success": False, "message": str(e)}

    def move_linear(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        """Linear Cartesian move (moveL). Blocks until motion is complete."""
        try:
            logger.info("Moving with moveL to '%s'", pose["name"])
            t   = self._pose_to_rotvec(pose, offset)
            spd = (speed or DEFAULT_SPEED) * MAX_LINEAR_SPEED
            acc = (speed or DEFAULT_SPEED) * MAX_LINEAR_ACCEL

            script = (
                f"movel(p[{t[0]:.6f},{t[1]:.6f},{t[2]:.6f},"
                f"{t[3]:.6f},{t[4]:.6f},{t[5]:.6f}],a={acc:.4f},v={spd:.4f})"
            )
            self._send_script(script)
            return self._wait_motion_complete()
        except Exception as e:
            logger.exception("moveL failed")
            return {"success": False, "message": str(e)}

    # ── Freedrive ─────────────────────────────────────────────────────────────

    def enable_freedrive(self) -> dict:
        """
        Enable freedrive (hand-guided) mode.
        Sends a looping URScript over a persistent socket — the robot stays in
        freedrive as long as the socket remains open. Call disable_freedrive() to exit.
        """
        try:
            self._freedrive_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._freedrive_sock.settimeout(SOCKET_TIMEOUT)
            self._freedrive_sock.connect((self.robot_ip, SCRIPT_PORT))
            self._freedrive_sock.sendall(
                "def freedrive():\n"
                "  freedrive_mode()\n"
                "  while True:\n"
                "    sync()\n"
                "  end\n"
                "end\n"
                "freedrive()\n".encode("utf-8")
            )
            logger.info("Freedrive enabled")
            return {"success": True, "message": "Freedrive enabled"}
        except Exception as e:
            logger.exception("Failed to enable freedrive")
            if self._freedrive_sock:
                self._freedrive_sock.close()
                self._freedrive_sock = None
            return {"success": False, "message": str(e)}

    def disable_freedrive(self) -> dict:
        """Exit freedrive mode and return the robot to normal operation."""
        try:
            if self._freedrive_sock:
                self._freedrive_sock.close()
                self._freedrive_sock = None
            reply = self._dashboard_cmd("stop")
            if "error" in reply.lower():
                return {"success": False, "message": f"Failed to stop freedrive: {reply}"}
            logger.info("Freedrive disabled")
            return {"success": True, "message": "Freedrive disabled"}
        except Exception as e:
            logger.exception("Failed to disable freedrive")
            return {"success": False, "message": str(e)}

    # ── Gripper ───────────────────────────────────────────────────────────────

    def _run_gripper_program(self, program: str) -> dict:
        """
        Load and execute a locally saved URP gripper program via the Dashboard Server.
        Waits GRIPPER_ACTUATE_TIME seconds for physical actuation, then stops the
        program if it is still running (some programs loop indefinitely).
        """
        try:
            reply = self._dashboard_cmd(f"load {program}")
            if "error" in reply.lower():
                return {"success": False, "message": f"Failed to load {program}: {reply}"}

            reply = self._dashboard_cmd("play")
            if "error" in reply.lower():
                return {"success": False, "message": f"Failed to play {program}: {reply}"}

            time.sleep(self.GRIPPER_ACTUATE_TIME)

            if "PLAYING" in self._dashboard_cmd("programstate").upper():
                self._dashboard_cmd("stop")

            return {"success": True}
        except Exception as e:
            logger.exception("Gripper program '%s' failed", program)
            return {"success": False, "message": str(e)}

    def gripper_open(self) -> dict:
        logger.info("Opening gripper")
        if self.gripper_state == 'open':
            return {"success": True, "message": "Gripper already open"}
        result = self._run_gripper_program(self.GRIPPER_OPEN_PROGRAM)
        if result["success"]:
            self.gripper_state = "open"
            return {"success": True, "message": "Gripper opened"}
        return result

    def gripper_close(self) -> dict:
        logger.info("Closing gripper")
        if self.gripper_state == 'close':
            return {"success": True, "message": "Gripper already closed"}
        result = self._run_gripper_program(self.GRIPPER_CLOSE_PROGRAM)
        if result["success"]:
            self.gripper_state = "closed"
            return {"success": True, "message": "Gripper closed"}
        return result

    # ── State ─────────────────────────────────────────────────────────────────

    def get_current_pose(self) -> dict:
        """
        Read the current robot pose from the real-time interface (port 30003).

        Opens a fresh connection each call to avoid mid-stream byte misalignment.
        Reads ~5 packets worth of data and scans for two consecutive valid packet
        headers to confirm alignment before decoding.

        Returns joint positions (rad) and TCP pose [x, y, z, qx, qy, qz, qw].
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(SOCKET_TIMEOUT)
                s.connect((self.robot_ip, STATE_PORT))
                buf = _recv_exactly(s, STATE_RECV_BYTES * 5)

            # Scan for a confirmed packet boundary by verifying two consecutive headers
            packet = None
            for i in range(len(buf) - 4):
                pkt_len = struct.unpack("!I", buf[i:i+4])[0]
                if not (1060 <= pkt_len <= STATE_RECV_BYTES):
                    continue
                next_pkt = i + pkt_len
                if next_pkt + 4 > len(buf):
                    continue
                if 1060 <= struct.unpack("!I", buf[next_pkt:next_pkt+4])[0] <= STATE_RECV_BYTES:
                    packet = buf[i:i+pkt_len]
                    break

            if packet is None:
                return {"success": False, "message": "Could not find a confirmed packet boundary in state stream"}

            joints = list(struct.unpack_from("!6d", packet, RT_JOINT_OFFSET))
            tcp_rv = list(struct.unpack_from("!6d", packet, RT_TCP_OFFSET))
            quat   = Rotation.from_rotvec(tcp_rv[3:]).as_quat().tolist()

            return {
                "success":         True,
                "joint_positions": joints,
                "pose":            tcp_rv[:3] + quat,
                "gripper_state":   self.gripper_state,
            }
        except Exception as e:
            logger.exception("Failed to read current pose")
            return {"success": False, "message": str(e)}