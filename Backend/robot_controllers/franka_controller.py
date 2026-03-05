# franka_controller.py
import atexit
import logging
import subprocess
import time
from typing import Optional

import moveit_commander
import rospy
from geometry_msgs.msg import Pose

from Backend.robot_controllers.base_robot_controller import BaseRobotController
from Backend.robot_controllers.franka_robot import FrankaRobot

logger = logging.getLogger("cobot_backend")

ROBOT_IP        = "192.168.1.100"
POSES_FILE      = "Backend/poses/franka_poses.jsonl"
ROS_LOG_FILE    = "Backend/logs/franka_ros.log"
LAUNCH_DELAY    = 10.0   # seconds to wait for ROS stack to be ready
DEFAULT_SPEED   = 1.0
MOVE_GROUP_NODE = "/move_group"


class FrankaController(BaseRobotController):

    def __init__(self):
        super().__init__(POSES_FILE)
        self._robot: Optional[FrankaRobot] = None
        self._ros_process: Optional[subprocess.Popen] = None
        self._roscpp_initialized: bool = False

    def connect(self) -> dict:
        """Start the MoveIt stack if needed, initialise rospy and MoveIt, and probe readiness."""
        try:
            if not self._roscpp_initialized:
                if self._is_move_group_running():
                    logger.info("MoveIt already running, skipping launch")
                else:
                    logger.info("Starting MoveIt stack")
                    self._launch_ros()
                rospy.init_node("speech_to_code_franka", anonymous=True)
                moveit_commander.roscpp_initialize([])
                self._roscpp_initialized = True
            else:
                if not self._is_move_group_running():
                    logger.info("Relaunching MoveIt stack")
                    self._launch_ros()
                else:
                    logger.info("Reusing existing ROS node and MoveIt stack")

            self._robot = FrankaRobot("panda_arm", "panda_hand", moveit_commander)

            deadline = time.time() + 10.0
            while time.time() < deadline:
                try:
                    self._robot.arm.get_current_joint_values()
                    break
                except Exception:
                    time.sleep(0.5)
            else:
                self._robot = None
                return {"success": False, "message": "MoveIt not responding after 10s"}

            self.connected = True
            logger.info("Connected successfully")
            return {"success": True, "message": "Franka connected"}

        except Exception as e:
            logger.exception("Connection failed")
            return {"success": False, "message": str(e)}

    def disconnect(self) -> None:
        """Kill the MoveIt stack. The rospy node is kept alive for reconnection."""
        self._kill_ros_process()
        self._robot = None
        self.connected = False
        logger.info("Disconnected successfully")

    def is_connected(self) -> bool:
        """Return True if the arm is reachable via MoveIt."""
        if not self._robot:
            return False
        try:
            self._robot.arm.get_current_joint_values()
            return True
        except Exception:
            return False

    def move_joint(self, pose: dict, speed: Optional[float] = None, offset: Optional[list] = None) -> dict:
        """Joint-space PTP move. Uses joint values when available and no offset is given."""
        logger.info("Moving with moveJ to '%s'", pose["name"])
        try:
            spd = speed or DEFAULT_SPEED
            if offset:
                logger.info("Offset used: %s", offset)
                self._robot.move_j(self._to_ros_pose(pose), spd, [x / 1000 for x in offset])
            elif pose.get("joints"):
                self._robot.move_j_joints(pose["joints"], spd)
            else:
                self._robot.move_j(self._to_ros_pose(pose), spd)
            return {"success": True, "message": "moveJ complete"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def move_linear(self, pose: dict, speed: Optional[float] = None, offset: Optional[list] = None) -> dict:
        """Linear Cartesian move."""
        logger.info("Moving with moveL to '%s'", pose["name"])
        try:
            spd = speed or DEFAULT_SPEED
            if offset:
                logger.info("Offset used: %s", offset)
            self._robot.move_l(
                self._to_ros_pose(pose),
                spd,
                [x / 1000 for x in offset] if offset else None,
            )
            return {"success": True, "message": "moveL complete"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def gripper_open(self) -> dict:
        """Open the Franka gripper."""
        try:
            logger.info("Opening gripper")
            self._robot.gripper_open()
            self.gripper_state = "open"
            return {"success": True, "message": "Gripper opened"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def gripper_close(self) -> dict:
        """Close the Franka gripper."""
        try:
            logger.info("Closing gripper")
            self._robot.gripper_close()
            self.gripper_state = "closed"
            return {"success": True, "message": "Gripper closed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def get_current_pose(self) -> dict:
        """Return current joint positions, TCP pose, and gripper state."""
        try:
            joints   = self._robot.arm.get_current_joint_values()
            ros_pose = self._robot.arm.get_current_pose().pose
            return {
                "success":         True,
                "joint_positions": list(joints),
                "pose": [
                    ros_pose.position.x,
                    ros_pose.position.y,
                    ros_pose.position.z,
                    ros_pose.orientation.x,
                    ros_pose.orientation.y,
                    ros_pose.orientation.z,
                    ros_pose.orientation.w,
                ],
                "gripper_state": self.gripper_state,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _to_ros_pose(self, pose_entry: dict) -> Pose:
        p = Pose()
        p.position.x    = pose_entry["pos"][0]
        p.position.y    = pose_entry["pos"][1]
        p.position.z    = pose_entry["pos"][2]
        p.orientation.x = pose_entry["quat"][0]
        p.orientation.y = pose_entry["quat"][1]
        p.orientation.z = pose_entry["quat"][2]
        p.orientation.w = pose_entry["quat"][3]
        return p

    def _kill_ros_process(self) -> None:
        if not self._ros_process:
            return
        self._ros_process.terminate()
        try:
            self._ros_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("ROS process did not exit cleanly, killing it")
            self._ros_process.kill()
            self._ros_process.wait()
        self._ros_process = None
        logger.info("MoveIt stack stopped")

    def _launch_ros(self) -> None:
        """Launch the MoveIt stack, in xterm if available, otherwise hidden."""
        if self._xterm_available():
            self._ros_process = subprocess.Popen(
                ["xterm", "-T", "ROS MoveIt Stack", "-e",
                 f"bash -c 'source ~/ws_moveit/devel/setup.bash && "
                 f"roslaunch panda_moveit_config franka_control.launch "
                 f"robot_ip:={ROBOT_IP} load_gripper:=true use_rviz:=false "
                 f"2>&1 | tee {ROS_LOG_FILE}; "
                 f"read -p \"ROS stopped - press Enter to close\"'"],
                start_new_session=True,
            )
            logger.info("MoveIt stack launched in separate xterm window")
        else:
            logger.warning("xterm not found — launching ROS hidden, output in %s", ROS_LOG_FILE)
            with open(ROS_LOG_FILE, "w") as log_file:
                self._ros_process = subprocess.Popen(
                    ["bash", "-c",
                     f"source ~/ws_moveit/devel/setup.bash && "
                     f"roslaunch panda_moveit_config franka_control.launch "
                     f"robot_ip:={ROBOT_IP} load_gripper:=true use_rviz:=false"],
                    stdout=log_file,
                    stderr=log_file,
                    start_new_session=True,
                )

        atexit.register(self._kill_ros_process)
        time.sleep(LAUNCH_DELAY)

    def _is_move_group_running(self) -> bool:
        try:
            result = subprocess.run(
                ["rosnode", "list"], capture_output=True, text=True, timeout=5
            )
            return MOVE_GROUP_NODE in result.stdout
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _xterm_available(self) -> bool:
        try:
            subprocess.run(["xterm", "-version"], capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False