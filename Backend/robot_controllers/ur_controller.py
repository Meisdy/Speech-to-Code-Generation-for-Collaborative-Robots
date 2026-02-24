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

DEFAULT_ROBOT_IP  = "169.254.70.80"
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
      - self._state_sock : Real-Time stream (30003)  – kept open for state polling
    URScript commands open a short-lived connection to port 30002 per command.
    """

    def __init__(
        self,
        robot_ip: str = DEFAULT_ROBOT_IP,
        poses_file: str = POSES_FILE,
    ):
        super().__init__(poses_file)
        self.robot_ip    = robot_ip
        self._dash_sock  : socket.socket | None = None
        self._state_sock : socket.socket | None = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> dict:
        try:
            # Dashboard socket (persistent)
            self._dash_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._dash_sock.settimeout(SOCKET_TIMEOUT)
            self._dash_sock.connect((self.robot_ip, DASHBOARD_PORT))
            # Consume the welcome banner ("Connected: Universal Robots …\n")
            self._dash_sock.recv(1024)

            # Real-time state socket (persistent, non-blocking recv later)
            self._state_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._state_sock.settimeout(SOCKET_TIMEOUT)
            self._state_sock.connect((self.robot_ip, STATE_PORT))

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
        for attr in ("_dash_sock", "_state_sock"):
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
        Each script must end with '\\n'.  The connection is closed immediately
        after sending; UR executes the commands asynchronously.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(SOCKET_TIMEOUT)
            s.connect((self.robot_ip, SCRIPT_PORT))
            if not script.endswith("\n"):
                script += "\n"
            s.sendall(script.encode("utf-8"))
            # Small delay so the robot starts receiving before we close
            time.sleep(0.05)

    # ── Motion helpers ────────────────────────────────────────────────────────

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

    # ── Motion ────────────────────────────────────────────────────────────────

    def move_joint(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        """
        Joint-space move (moveJ).
        Uses stored joint angles unless an offset is supplied,
        in which case inverse kinematics via moveJ with a pose target is used.
        """
        try:
            spd = (speed or DEFAULT_SPEED) * MAX_JOINT_SPEED
            acc = (speed or DEFAULT_SPEED) * MAX_JOINT_ACCEL

            if offset:
                target = self._pose_to_rotvec(pose, offset)
                # moveJ with a pose argument (UR does IK internally)
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
            return {"success": True, "message": "moveJ sent"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def move_linear(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        """Linear Cartesian move (moveL)."""
        try:
            target = self._pose_to_rotvec(pose, offset)
            spd    = (speed or DEFAULT_SPEED) * MAX_LINEAR_SPEED
            acc    = (speed or DEFAULT_SPEED) * MAX_LINEAR_ACCEL

            script = (
                f"movel(p[{target[0]:.6f},{target[1]:.6f},{target[2]:.6f},"
                f"{target[3]:.6f},{target[4]:.6f},{target[5]:.6f}],"
                f"a={acc:.4f},v={spd:.4f})"
            )
            self._send_script(script)
            return {"success": True, "message": "moveL sent"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ── Gripper (stub) ────────────────────────────────────────────────────────

    def gripper_open(self) -> dict:
        """TODO: implement gripper open for your hardware."""
        self.gripper_state = "open"
        return {"success": True, "message": "Gripper open (stub — not implemented)"}

    def gripper_close(self) -> dict:
        """TODO: implement gripper close for your hardware."""
        self.gripper_state = "closed"
        return {"success": True, "message": "Gripper close (stub — not implemented)"}

    # ── State ─────────────────────────────────────────────────────────────────

    def get_current_state(self) -> dict:
        """
        Read one state packet from the real-time interface (port 30003) and
        decode joint positions and TCP pose.

        The 125 Hz stream delivers packets continuously; we flush the socket
        buffer and grab the most recent complete packet.

        Packet layout (big-endian doubles):
            offset 252 : 6 joint positions [rad]
            offset 444 : TCP pose [x, y, z, rx, ry, rz]  (rotvec, metres)
        """
        try:
            # Drain everything in the buffer and keep only the last full packet.
            # Set a short timeout so we don't block forever.
            self._state_sock.settimeout(0.1)
            raw = b""
            try:
                while True:
                    chunk = self._state_sock.recv(STATE_RECV_BYTES * 2)
                    if chunk:
                        raw += chunk
            except socket.timeout:
                pass
            finally:
                self._state_sock.settimeout(SOCKET_TIMEOUT)

            if len(raw) < STATE_RECV_BYTES:
                # Buffer was empty or incomplete — do a blocking read for one packet
                self._state_sock.settimeout(SOCKET_TIMEOUT)
                raw = _recv_exactly(self._state_sock, STATE_RECV_BYTES)

            # Use the LAST complete packet in the buffer
            pkt_len = STATE_RECV_BYTES  # 1220 for e-Series, works as upper bound
            # Detect actual packet size from the first 4-byte big-endian int header
            if len(raw) >= 4:
                pkt_len = struct.unpack("!I", raw[:4])[0]
                # Clamp to sensible range
                pkt_len = max(1060, min(pkt_len, STATE_RECV_BYTES))

            # Align to the last complete packet
            if len(raw) >= pkt_len:
                offset = ((len(raw) - pkt_len) // pkt_len) * pkt_len
                packet = raw[offset: offset + pkt_len]
            else:
                packet = raw  # best effort

            # Decode joints (6 × double starting at byte 252)
            joints = list(struct.unpack_from("!6d", packet, RT_JOINT_OFFSET))

            # Decode TCP rotvec (6 × double starting at byte 444)
            tcp_rv = list(struct.unpack_from("!6d", packet, RT_TCP_OFFSET))
            quat   = Rotation.from_rotvec(tcp_rv[3:]).as_quat().tolist()
            pose   = tcp_rv[:3] + quat  # [x, y, z, qx, qy, qz, qw]

            return {
                "success":         True,
                "joint_positions": joints,
                "pose":            pose,
                "gripper_state":   self.gripper_state,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}