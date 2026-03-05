# franka_robot.py
# Based on robot.py by Plipking (https://github.com/Plipking/FrankaEmika_AssemblyCell)
# Original license: MIT
# Modified by Sandy Meister, 2026

import numpy as np
from geometry_msgs.msg import Pose
from moveit_commander.exception import MoveItCommanderException


class FrankaRobot:
    """Pure motion executor for the Franka Panda via ROS / MoveIt.

    This class has no knowledge of named poses or files — it receives ready-to-use
    objects from FrankaController and forwards them to MoveIt.
    """

    def __init__(self, arm_name, hand_name, moveit_commander):
        self.arm     = moveit_commander.MoveGroupCommander(arm_name)
        self.gripper = moveit_commander.MoveGroupCommander(hand_name)

        self.arm.set_goal_orientation_tolerance(0.005)
        self.arm.set_goal_position_tolerance(0.005)
        self.set_mode_ptp()

    # --------------------------
    #       PLANNERS
    # --------------------------

    def set_mode_ptp(self):
        self.arm.set_planner_id("PTP")
        self.arm.set_planning_pipeline_id("pilz_industrial_motion_planner")
        self.arm.set_max_velocity_scaling_factor(1.0)
        self.arm.set_max_acceleration_scaling_factor(1.0)

    def set_mode_lin(self):
        self.arm.set_planner_id("LIN")
        self.arm.set_planning_pipeline_id("pilz_industrial_motion_planner")
        self.arm.set_max_velocity_scaling_factor(0.1)
        self.arm.set_max_acceleration_scaling_factor(0.1)

    # --------------------------
    #     MOTION FUNCTIONS
    # --------------------------

    def MoveL(self, pose: Pose, offset=None):
        self.set_mode_lin()
        self._go_to_pose(pose, offset)

    def MoveJ(self, pose: Pose, offset=None):
        self.set_mode_ptp()
        self._go_to_pose(pose, offset)

    def MoveJ_J(self, joints: list):
        """Joint-space PTP move using a list of joint values."""
        if joints is None:
            raise MoveItCommanderException("No joint data provided.")

        self.set_mode_ptp()
        self.arm.set_joint_value_target(joints)

        success = self.arm.go(wait=True)
        self.arm.stop()
        self.arm.clear_pose_targets()

        if not success:
            raise MoveItCommanderException("Joint PTP failed.")

    # --------------------------
    #   INTERNAL POSE MOVE
    # --------------------------

    def _go_to_pose(self, pose: Pose, offset=None):
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

    # --------------------------
    #      GRIPPER
    # --------------------------

    def gripper_open(self, width: float = 0.06):
        self._set_width(width)

    def gripper_close(self):
        self._set_width(0.0005)

    def _set_width(self, width: float):
        target = width / 2.0
        self.gripper.set_joint_value_target("panda_finger_joint1", target)
        self.gripper.set_joint_value_target("panda_finger_joint2", target)
        self.gripper.go(wait=True)

    # --------------------------
    #      UTILITIES
    # --------------------------

    def _normalize_quaternion(self, pose: Pose):
        q = np.array([
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w
        ])
        norm = np.linalg.norm(q)
        if norm > 0:
            q /= norm
            pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w = q