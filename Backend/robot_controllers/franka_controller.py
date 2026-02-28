# franka_controller.py
import subprocess
import time
import logging

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
        self._robot             = None
        self._ros_process       = None

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    def connect(self) -> dict:
        try:
            if self._is_move_group_running():
                logger.info("Franka: MoveIt already running, skipping launch")
            else:
                logger.info("Franka: Starting MoveIt stack")
                self._launch_ros()

            rospy.init_node("speech_to_code_franka", anonymous=True)
            moveit_commander.roscpp_initialize([])
            logger.debug("Franka: MoveIt commander initialized")

            self._robot    = FrankaRobot("panda_arm", "panda_hand", moveit_commander, POSES_FILE)
            self.connected = True

            logger.info("Franka: Connected successfully")
            return {"success": True, "message": "Franka connected"}

        except Exception as e:
            logger.error("Franka: Error while connecting - %s", e)
            return {"success": False, "message": str(e)}

    def disconnect(self) -> None:
        try:
            moveit_commander.roscpp_shutdown()
        except Exception as e:
            logger.warning("Franka: roscpp_shutdown error - %s", e)

        if self._ros_process:
            self._ros_process.terminate()
            self._ros_process.wait()
            logger.info("Franka: MoveIt stack stopped")

        self._robot = None
        self._ros_process = None
        self.connected = False
        logger.info("Franka: Disconnected successfully")

    def is_connected(self) -> bool:
        if not self._robot:
            return False
        try:
            self._robot.arm.get_current_joint_values()
            return True
        except Exception:
            return False

    def _is_move_group_running(self) -> bool:
        """Check if /move_group node is active on the ROS master."""
        try:
            result = subprocess.run(
                ["rosnode", "list"],
                capture_output=True, text=True, timeout=5
            )
            return MOVE_GROUP_NODE in result.stdout
        except Exception:
            return False

    def _launch_ros(self) -> None:
        """Launch the MoveIt stack as a background process, logging to file."""
        with open(ROS_LOG_FILE, "w") as log_file:
            self._ros_process = subprocess.Popen(
                ["bash", "-c",
                 f"source ~/ws_moveit/devel/setup.bash && "
                 f"roslaunch panda_moveit_config franka_control.launch "
                 f"robot_ip:={ROBOT_IP} load_gripper:=true use_rviz:=false"],
                stdout=log_file,
                stderr=log_file
            )
        time.sleep(LAUNCH_DELAY)

    # ------------------------------------------------------------------ #
    # Motion
    # ------------------------------------------------------------------ #

    def move_joint(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        try:
            if speed:
                self._robot.arm.set_max_velocity_scaling_factor(speed)
                self._robot.arm.set_max_acceleration_scaling_factor(speed)
            if offset:
                self._robot.MoveJ(pose["name"], offset=offset)
            else:
                self._robot.MoveJ_J(pose["name"])
            return {"success": True, "message": "moveJ complete"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def move_linear(self, pose: dict, speed: float = None, offset: list = None) -> dict:
        try:
            if speed:
                self._robot.arm.set_max_velocity_scaling_factor(speed)
                self._robot.arm.set_max_acceleration_scaling_factor(speed)
            self._robot.MoveL(pose["name"], offset=offset)
            return {"success": True, "message": "moveL complete"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ------------------------------------------------------------------ #
    # Gripper
    # ------------------------------------------------------------------ #

    def gripper_open(self) -> dict:
        try:
            self._robot.gripper_open()
            self.gripper_state = "open"
            return {"success": True, "message": "Gripper opened"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def gripper_close(self) -> dict:
        try:
            self._robot.gripper_close()
            self.gripper_state = "closed"
            return {"success": True, "message": "Gripper closed"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def get_current_pose(self) -> dict:
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