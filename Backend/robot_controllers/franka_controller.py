# franka_controller.py
import atexit
import logging
import os
import subprocess
import time
from typing import Optional

import moveit_commander
import rospy

from Backend.robot_controllers.base_robot_controller import BaseRobotController
from Backend.robot_controllers.franka_robot import FrankaRobot

logger = logging.getLogger("cobot_backend")

ROBOT_IP        = "192.168.1.100"
POSES_FILE      = "Backend/poses/franka_poses.jsonl"
ROS_LOG_FILE    = "Backend/logs/franka_ros.log"
LAUNCH_DELAY    = 10.0  # seconds to wait for ROS stack to be ready
MOVE_GROUP_NODE = "/move_group"


class FrankaController(BaseRobotController):

    def __init__(self):
        super().__init__(POSES_FILE)
        self._robot              = None
        self._ros_process        = None
        self._roscpp_initialized = False

    def connect(self) -> dict:
        """Connect to the Franka, launching MoveIt if not already running."""
        try:
            if self._is_move_group_running():
                logger.info("MoveIt already running, skipping launch")
            else:
                logger.info("Starting MoveIt stack")
                self._launch_ros()

            # rosconsole opens its stdout handle during rospy.init_node(), so
            # the fd 1 redirect must wrap it — doing it after is too late.
            # All three calls are inside the same window so no [INFO] lines
            # from roscpp or MoveGroupCommander reach the terminal.
            saved_stdout_fd = os.dup(1)
            try:
                with open(ROS_LOG_FILE, "a") as log_file:
                    os.dup2(log_file.fileno(), 1)
                rospy.init_node("speech_to_code_franka", anonymous=True)
                moveit_commander.roscpp_initialize([])
                self._roscpp_initialized = True
                self._robot = FrankaRobot("panda_arm", "panda_hand", moveit_commander, POSES_FILE)
            finally:
                os.dup2(saved_stdout_fd, 1)
                os.close(saved_stdout_fd)

            self.connected = True

            logger.info("Connected successfully")
            return {"success": True, "message": "Franka connected"}

        except Exception as e:
            logger.error("Error while connecting - %s", e)
            return {"success": False, "message": str(e)}

    def disconnect(self) -> None:
        """Shut down MoveIt commander and terminate the ROS stack if we launched it."""
        # The xmlrpc-c C++ library calls fprintf(stderr) directly — it has no
        # configurable logger, so the only way to silence it is at the fd level.
        # We point fd 2 at /dev/null for the shutdown window only, then restore it.
        old_stderr_fd = os.dup(2)
        try:
            with open(os.devnull, "w") as devnull:
                os.dup2(devnull.fileno(), 2)

            try:
                rospy.signal_shutdown("FrankaController disconnecting")
            except Exception as e:
                logger.warning("rospy.signal_shutdown error - %s", e)

            if self._roscpp_initialized:
                try:
                    moveit_commander.roscpp_shutdown()
                except Exception as e:
                    logger.warning("roscpp_shutdown error - %s", e)
                self._roscpp_initialized = False

        finally:
            os.dup2(old_stderr_fd, 2)
            os.close(old_stderr_fd)

        self._kill_ros_process()

        self._robot    = None
        self.connected = False
        logger.info("Disconnected successfully")

    def _kill_ros_process(self) -> None:
        """Terminate the roslaunch child process if we own it."""
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

    def save_pose(self, name: str, overwrite: bool = False) -> dict:
        """Save pose and sync into FrankaRobot._positions so it is immediately usable."""
        result = super().save_pose(name, overwrite)
        if result["success"] and self._robot:
            entry = self.poses[name]
            from geometry_msgs.msg import Pose
            pose = Pose()
            pose.position.x    = entry["pos"][0]
            pose.position.y    = entry["pos"][1]
            pose.position.z    = entry["pos"][2]
            pose.orientation.x = entry["quat"][0]
            pose.orientation.y = entry["quat"][1]
            pose.orientation.z = entry["quat"][2]
            pose.orientation.w = entry["quat"][3]
            self._robot._positions[name] = {"pose": pose, "joints": entry.get("joints")}
        return result

    def delete_pose(self, name: str) -> dict:
        """Delete pose and remove from FrankaRobot._positions immediately."""
        result = super().delete_pose(name)
        if result["success"] and self._robot:
            self._robot._positions.pop(name, None)
        return result

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
        """Execute a joint-space move to the given pose."""
        logger.info("Moving with moveJ to '%s'", pose["name"])
        
        try:
            if speed:
                self._robot.arm.set_max_velocity_scaling_factor(speed)
                self._robot.arm.set_max_acceleration_scaling_factor(speed)
            if offset:
                logger.info(f"Offset used: {offset}")
                offset = [x / 1000 for x in offset] # Switch to m for backend module
                self._robot.MoveJ(pose["name"], offset=offset)
            else:
                self._robot.MoveJ_J(pose["name"])
            return {"success": True, "message": "moveJ complete"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def move_linear(self, pose: dict, speed: Optional[float] = None, offset: Optional[list] = None) -> dict:
        """Execute a linear Cartesian move to the given pose."""
        logger.info("Moving with moveL to '%s'", pose["name"])
        if offset:
            logger.info(f"Offset used: {offset}")   
            offset = [x / 1000 for x in offset] # Switch to m for backend module
        try:
            if speed:
                self._robot.arm.set_max_velocity_scaling_factor(speed)
                self._robot.arm.set_max_acceleration_scaling_factor(speed)
            self._robot.MoveL(pose["name"], offset)
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

            pose = [
                ros_pose.position.x,
                ros_pose.position.y,
                ros_pose.position.z,
                ros_pose.orientation.x,
                ros_pose.orientation.y,
                ros_pose.orientation.z,
                ros_pose.orientation.w,
            ]

            return {
                "success":         True,
                "joint_positions": list(joints),
                "pose":            pose,
                "gripper_state":   self.gripper_state,
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def _is_move_group_running(self) -> bool:
        """Check if /move_group node is active on the ROS master."""
        try:
            result = subprocess.run(
                ["rosnode", "list"],
                capture_output=True, text=True, timeout=5
            )
            return MOVE_GROUP_NODE in result.stdout
        except (subprocess.TimeoutExpired, OSError):
            return False

    def _launch_ros(self) -> None:
        """Launch the MoveIt stack in a separate xterm window.

        Using xterm keeps all ROS and xmlrpc-c output out of the backend terminal.
        xterm's PID is tracked so we can shut it down cleanly without sending
        signals to the backend process group. Falls back to a hidden background
        process (with start_new_session=True) if xterm is not available.
        """
        if self._xterm_available():
            # Run roslaunch inside xterm; tee mirrors output to the log file too.
            # 'read' at the end keeps the window open so the user can see any
            # final ROS output before it disappears.
            self._ros_process = subprocess.Popen(
                ["xterm", "-T", "ROS MoveIt Stack", "-e",
                 "bash -c '"
                 "source ~/ws_moveit/devel/setup.bash && "
                 f"roslaunch panda_moveit_config franka_control.launch "
                 f"robot_ip:={ROBOT_IP} load_gripper:=true use_rviz:=false "
                 f"2>&1 | tee {ROS_LOG_FILE}; "
                 "read -p \"ROS stopped - press Enter to close\"'"],
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
                    # Isolate from Ctrl+C so the backend terminal stays clean.
                    start_new_session=True,
                )

        atexit.register(self._kill_ros_process)
        time.sleep(LAUNCH_DELAY)

    def _xterm_available(self) -> bool:
        """Return True if xterm is installed on this machine."""
        try:
            subprocess.run(["xterm", "-version"], capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False