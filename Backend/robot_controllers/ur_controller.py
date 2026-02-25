"""
URController — pure TCP/IP socket implementation for UR10 (and compatible UR cobots).

Port layout
-----------
  29999  Dashboard Server   : text-based admin commands (power, brake-release, play/stop)
  30002  Secondary Client   : send URScript commands (10 Hz state stream, ignored here)
  30003  Real-Time Client   : 125 Hz binary state stream – joints & TCP pose are read here

Gripper
-------
  All OnRobot / gripper code has been removed.
  Add your own gripper implementation and hook it into gripper_open() / gripper_close().

Motion notes
------------
  moveJ / moveL are sent as URScript text to port 30002.
  Speeds and accelerations are in rad/s (joint) and m/s (linear), not fractions,
  so the DEFAULT_SPEED fraction is scaled against the same MAX_* constants as before.

State packet (port 30003, CB3 / e-Series)
------------------------------------------
  The real-time packet is 1060 bytes (CB3) or 1220 bytes (e-Series).
  Offsets used here (big-endian doubles, 8 bytes each):
      252 … 299   actual joint positions  q[0..5]
      444 … 491   actual TCP pose         [x, y, z, rx, ry, rz]  (rotvec, metres)
  Reference: UR Client Interface documentation v3 / v5.
"""

import socket
import struct
import time
from scipy.spatial.transform import Rotation

from Backend.robot_controllers.base_robot_controller import BaseRobotController


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_ROBOT_IP  = "192.168.1.100"
POSES_FILE        = "Backend/poses/ur_poses.jsonl"

DASHBOARD_PORT    = 29999   # text, admin
SCRIPT_PORT       = 30002   # URScript commands
STATE_PORT        = 30003   # 125 Hz binary state stream

SOCKET_TIMEOUT    = 5.0     # seconds
STATE_RECV_BYTES  = 1220    # large enough for both CB3 (1060) and e-Series (1220)

# Real-time packet byte offsets (big-endian double = 8 bytes each)
RT_JOINT_OFFSET   = 252     # 6 × double  → actual joint positions [rad]
RT_TCP_OFFSET     = 444     # 6 × double  → actual TCP [x,y,z,rx,ry,rz]

MAX_JOINT_SPEED   = 3.14    # rad/s
MAX_JOINT_ACCEL   = 3.14    # rad/s²
MAX_LINEAR_SPEED  = 0.5     # m/s
MAX_LINEAR_ACCEL  = 0.5     # m/s²
DEFAULT_SPEED     = 0.5     # fraction 0.0–1.0


# ── Helper ─────────────────────────────────────────────────────────────────────

def _recv_exactly(sock: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes from *sock*, blocking until done."""
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

    Connections maintained while connected:
      - self._dash_sock  : Dashboard Server (29999) – kept open for status queries
    URScript commands open a short-lived connection to port 30002 per command.
    State is read by opening a fresh connection to port 30003 per call.
    """

    def __init__(self, robot_ip: str = DEFAULT_ROBOT_IP, poses_file: str = POSES_FILE):
        super().__init__(poses_file)
        self.robot_ip    = robot_ip
        self._dash_sock  : socket.socket | None = None
        self._freedrive_sock : socket.socket | None = None

    # ── Connection methods ────────────────────────────────────────────────────────────

    def connect(self) -> dict:
        try:
            self._dash_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._dash_sock.settimeout(SOCKET_TIMEOUT)
            self._dash_sock.connect((self.robot_ip, DASHBOARD_PORT))
            # Consume the welcome banner ("Connected: Universal Robots …\n")
            self._dash_sock.recv(1024)

            self.connected = True
            return {"success": True, "message": "Connected"}
        except Exception as e:
            self._close_sockets()
            return {"success": False, "message": str(e)}

    def disconnect(self) -> dict:
        try:
            self._close_sockets()
            self.connected = False
            return {"success": True, "message": "Disconnected"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def is_connected(self) -> bool:
        if not self.connected:
            return False
        try:
            reply = self._dashboard_cmd("robotmode")
            return reply.upper().startswith("ROBOTMODE")
        except Exception:
            return False

    def _close_sockets(self):
        for attr in ("_dash_sock", "_freedrive_sock"):
            sock = getattr(self, attr, None)
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
            setattr(self, attr, None)

    # ── Dashboard helpers ─────────────────────────────────────────────────────

    def _dashboard_cmd(self, cmd: str) -> str:
        """Send a Dashboard Server command and return the single-line reply."""
        self._dash_sock.sendall((cmd + "\n").encode("utf-8"))
        return self._dash_sock.recv(1024).decode("utf-8").strip()

    # ── URScript sender ───────────────────────────────────────────────────────

    def _send_script(self, script: str):
        """
        Open a fresh connection to port 30002, send *script*, then close.
        Each script must end with '\\n'. The connection is closed immediately
        after sending; UR executes the commands asynchronously.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(SOCKET_TIMEOUT)
            s.connect((self.robot_ip, SCRIPT_PORT))
            if not script.endswith("\n"):
                script += "\n"
            s.sendall(script.encode("utf-8"))
            time.sleep(0.05)

    # ── Motion helpers ────────────────────────────────────────────────────────

    MOTION_TIMEOUT = 30.0  # seconds before giving up waiting
    MOTION_POLL_INTERVAL = 0.1  # seconds between position checks
    MOTION_THRESHOLD = 0.001  # rad — joints considered stopped below this delta


    @staticmethod
    def _pose_to_rotvec(pose: dict, offset: list | None = None) -> list:
        """Convert stored pose dict (pos + quat) → [x, y, z, rx, ry, rz]."""
        pos    = list(pose["pos"])
        rotvec = Rotation.from_quat(pose["quat"]).as_rotvec().tolist()
        if offset:
            pos[0] += offset[0]
            pos[1] += offset[1]
            pos[2] += offset[2]
        return pos + rotvec

    def _wait_motion_complete(self) -> dict:
        """
        Block until joint positions stop changing, indicating motion is complete.
        Compares two consecutive reads — if all joints move less than
        MOTION_THRESHOLD between reads the robot is considered stationary.
        """
        deadline = time.time() + self.MOTION_TIMEOUT
        # Give the robot a moment to actually start moving before we poll
        time.sleep(0.3)

        prev_joints = None
        while time.time() < deadline:
            state = self.get_current_state()
            if not state["success"]:
                return {"success": False, "message": f"State read failed while waiting for motion: {state['message']}"}
            curr_joints = state["joint_positions"]
            if prev_joints is not None:
                deltas = [abs(c - p) for c, p in zip(curr_joints, prev_joints)]
                if all(d < self.MOTION_THRESHOLD for d in deltas):
                    return {"success": True}
            prev_joints = curr_joints
            time.sleep(self.MOTION_POLL_INTERVAL)

        return {"success": False, "message": f"Motion did not complete within {self.MOTION_TIMEOUT}s"}

    # ── Motion ────────────────────────────────────────────────────────────────

    def move_joint(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        try:
            spd = (speed or DEFAULT_SPEED) * MAX_JOINT_SPEED
            acc = (speed or DEFAULT_SPEED) * MAX_JOINT_ACCEL

            if offset:
                target = self._pose_to_rotvec(pose, offset)
                script = (
                    f"movej(p[{target[0]:.6f},{target[1]:.6f},{target[2]:.6f},"
                    f"{target[3]:.6f},{target[4]:.6f},{target[5]:.6f}],"
                    f"a={acc:.4f},v={spd:.4f})"
                )
            else:
                j = pose["joints"]
                script = (
                    f"movej([{j[0]:.6f},{j[1]:.6f},{j[2]:.6f},"
                    f"{j[3]:.6f},{j[4]:.6f},{j[5]:.6f}],"
                    f"a={acc:.4f},v={spd:.4f})"
                )

            self._send_script(script)
            return self._wait_motion_complete()
        except Exception as e:
            return {"success": False, "message": str(e)}

    def move_linear(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        try:
            target = self._pose_to_rotvec(pose, offset)
            spd = (speed or DEFAULT_SPEED) * MAX_LINEAR_SPEED
            acc = (speed or DEFAULT_SPEED) * MAX_LINEAR_ACCEL

            script = (
                f"movel(p[{target[0]:.6f},{target[1]:.6f},{target[2]:.6f},"
                f"{target[3]:.6f},{target[4]:.6f},{target[5]:.6f}],"
                f"a={acc:.4f},v={spd:.4f})"
            )
            self._send_script(script)
            return self._wait_motion_complete()
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ── Freedrive ─────────────────────────────────────────────────────────────

    def enable_freedrive(self) -> dict:
        try:
            mode = self._dashboard_cmd("robotmode")
            print(f"robot mode: {repr(mode)}")

            safety = self._dashboard_cmd("safetystatus")
            print(f"safety status: {repr(safety)}")

            if "RUNNING" not in mode.upper():
                self._dashboard_cmd("power on")
                time.sleep(3)
                self._dashboard_cmd("brake release")
                time.sleep(2)

            self._freedrive_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._freedrive_sock.settimeout(SOCKET_TIMEOUT)
            self._freedrive_sock.connect((self.robot_ip, SCRIPT_PORT))

            script = (
                "def freedrive():\n"
                "  freedrive_mode()\n"
                "  while True:\n"
                "    sync()\n"
                "  end\n"
                "end\n"
                "freedrive()\n"
            )
            self._freedrive_sock.sendall(script.encode("utf-8"))
            print(f"script sent")

            time.sleep(0.5)
            mode_after = self._dashboard_cmd("programstate")
            print(f"program state after: {repr(mode_after)}")

            return {"success": True, "message": "Freedrive enabled"}
        except Exception as e:
            if self._freedrive_sock:
                self._freedrive_sock.close()
                self._freedrive_sock = None
            return {"success": False, "message": str(e)}

    def disable_freedrive(self) -> dict:
        try:
            if self._freedrive_sock:
                self._freedrive_sock.close()
                self._freedrive_sock = None
            reply = self._dashboard_cmd("stop")
            if "error" in reply.lower():
                return {"success": False, "message": f"Failed to stop freedrive: {reply}"}
            return {"success": True, "message": "Freedrive disabled"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ── Gripper ───────────────────────────────────────────────────────────────

    GRIPPER_OPEN_PROGRAM  = "open_UG2_Gripper.urp"
    GRIPPER_CLOSE_PROGRAM = "close_UG2_Gripper.urp"
    GRIPPER_TIMEOUT       = 10.0   # seconds to wait for program completion
    GRIPPER_POLL_INTERVAL = 0.1    # seconds between programstate polls
    GRIPPER_ACTUATE_TIME  = 4.0  # seconds to wait for physical actuation

    def _run_gripper_program(self, program: str) -> dict:
        try:
            reply = self._dashboard_cmd(f"load {program}")
            if "error" in reply.lower():
                return {"success": False, "message": f"Failed to load {program}: {reply}"}

            reply = self._dashboard_cmd("play")
            if "error" in reply.lower():
                return {"success": False, "message": f"Failed to play {program}: {reply}"}

            # Always wait the full actuation time for the gripper to physically move
            time.sleep(self.GRIPPER_ACTUATE_TIME)

            # Then stop the program in case it's still running (e.g. close program loops)
            state = self._dashboard_cmd("programstate")
            if "PLAYING" in state.upper():
                self._dashboard_cmd("stop")

            return {"success": True}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def gripper_open(self) -> dict:
        result = self._run_gripper_program(self.GRIPPER_OPEN_PROGRAM)
        if result["success"]:
            self.gripper_state = "open"
            return {"success": True, "message": "Gripper opened"}
        return result

    def gripper_close(self) -> dict:
        result = self._run_gripper_program(self.GRIPPER_CLOSE_PROGRAM)
        if result["success"]:
            self.gripper_state = "closed"
            return {"success": True, "message": "Gripper closed"}
        return result

    # ── State ─────────────────────────────────────────────────────────────────

    def get_current_state(self) -> dict:
        """
        Read one state packet from the real-time interface (port 30003) and
        decode joint positions and TCP pose.

        Opens a fresh connection each call to avoid mid-stream misalignment.
        Reads a large buffer and scans for a confirmed packet boundary by
        verifying two consecutive packet headers.

        Packet layout (big-endian doubles):
            offset 252 : 6 joint positions [rad]
            offset 444 : TCP pose [x, y, z, rx, ry, rz]  (rotvec, metres)
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(SOCKET_TIMEOUT)
                s.connect((self.robot_ip, STATE_PORT))
                # Read enough for ~5 packets to guarantee we capture at least
                # two consecutive complete ones for reliable boundary detection
                buf = _recv_exactly(s, STATE_RECV_BYTES * 5)

            # Scan for a confirmed packet boundary by checking two consecutive
            # packet length headers. This handles connecting mid-stream.
            packet = None
            for i in range(len(buf) - 4):
                pkt_len = struct.unpack("!I", buf[i:i+4])[0]
                if not (1060 <= pkt_len <= STATE_RECV_BYTES):
                    continue
                next_pkt = i + pkt_len
                if next_pkt + 4 > len(buf):
                    continue
                next_len = struct.unpack("!I", buf[next_pkt:next_pkt+4])[0]
                if 1060 <= next_len <= STATE_RECV_BYTES:
                    # Two consecutive valid headers — we're aligned
                    packet = buf[i:i+pkt_len]
                    break

            if packet is None:
                return {"success": False, "message": "Could not find confirmed packet boundary"}

            joints = list(struct.unpack_from("!6d", packet, RT_JOINT_OFFSET))
            tcp_rv = list(struct.unpack_from("!6d", packet, RT_TCP_OFFSET))
            quat   = Rotation.from_rotvec(tcp_rv[3:]).as_quat().tolist()
            pose   = tcp_rv[:3] + quat

            return {
                "success":         True,
                "joint_positions": joints,
                "pose":            pose,
                "gripper_state":   self.gripper_state,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}