# franka_robot.py
# Based on robot.py by Plipking (https://github.com/Plipking/FrankaEmika_AssemblyCell)
# Original license: MIT
# Modified by Sandy Meister, 2026

import numpy as np

LIN_MAX_SPEED = 0.2  # Pilz LIN planner requires low scaling to reliably find plans
from geometry_msgs.msg import Pose
from moveit_commander.exception import MoveItCommanderException


class FrankaRobot:
    """Pure motion executor for the Franka Panda via ROS / MoveIt.

    Receives ready-to-use Pose objects and joint lists from FrankaController
    and forwards them to MoveIt. Has no knowledge of named poses or files.
    """

    def __init__(self, arm_name: str, hand_name: str, moveit_commander):
        self.arm     = moveit_commander.MoveGroupCommander(arm_name)
        self.gripper = moveit_commander.MoveGroupCommander(hand_name)

        self.arm.set_goal_orientation_tolerance(0.005)
        self.arm.set_goal_position_tolerance(0.005)
        self._set_mode_ptp()

    def move_j(self, pose: Pose, speed: float, offset: list = None) -> None:
        """PTP move to a Cartesian pose."""
        self._set_mode_ptp()
        self._apply_speed(speed)
        self._go_to_pose(pose, offset)

    def move_l(self, pose: Pose, speed: float, offset: list = None) -> None:
        """Linear Cartesian move to a pose. Speed is capped — the Pilz LIN planner
        requires low velocity/acceleration scaling to find valid plans."""
        self._set_mode_lin()
        self._apply_speed(min(speed, LIN_MAX_SPEED))
        self._go_to_pose(pose, offset)

    def move_j_joints(self, joints: list, speed: float) -> None:
        """Joint-space PTP move using a list of joint values."""
        self._set_mode_ptp()
        self._apply_speed(speed)
        self.arm.set_joint_value_target(joints)

        success = self.arm.go(wait=True)
        self.arm.stop()
        self.arm.clear_pose_targets()

        if not success:
            raise MoveItCommanderException("Joint PTP failed.")

    def gripper_open(self, width: float = 0.06) -> None:
        """Open the gripper to the given width in metres."""
        self._set_gripper_width(width)

    def gripper_close(self) -> None:
        """Close the gripper."""
        self._set_gripper_width(0.0005)

    def _set_mode_ptp(self) -> None:
        self.arm.set_planner_id("PTP")
        self.arm.set_planning_pipeline_id("pilz_industrial_motion_planner")

    def _set_mode_lin(self) -> None:
        self.arm.set_planner_id("LIN")
        self.arm.set_planning_pipeline_id("pilz_industrial_motion_planner")

    def _apply_speed(self, speed: float) -> None:
        self.arm.set_max_velocity_scaling_factor(speed)
        self.arm.set_max_acceleration_scaling_factor(speed)

    def _go_to_pose(self, pose: Pose, offset: list = None) -> None:
        pose_goal = Pose()
        pose_goal.position.x  = pose.position.x
        pose_goal.position.y  = pose.position.y
        pose_goal.position.z  = pose.position.z
        pose_goal.orientation = pose.orientation

        if offset:
            pose_goal.position.x += offset[0]
            pose_goal.position.y += offset[1]
            pose_goal.position.z += offset[2]

        self._normalize_quaternion(pose_goal)
        self.arm.set_pose_target(pose_goal)

        success = self.arm.go(wait=True)
        self.arm.stop()
        self.arm.clear_pose_targets()

        if not success:
            raise MoveItCommanderException("Pose PTP/LIN failed.")

    def _set_gripper_width(self, width: float) -> None:
        target = width / 2.0
        self.gripper.set_joint_value_target("panda_finger_joint1", target)
        self.gripper.set_joint_value_target("panda_finger_joint2", target)
        self.gripper.go(wait=True)

    def _normalize_quaternion(self, pose: Pose) -> None:
        q = np.array([
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w,
        ])
        norm = np.linalg.norm(q)
        if norm > 0:
            q /= norm
            pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w = q