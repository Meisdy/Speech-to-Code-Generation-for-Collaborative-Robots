# franka_robot.py
# Based on robot.py by Plipking (https://github.com/Plipking/FrankaEmika_AssemblyCell)
# Original license: MIT
# Modified by Sandy Meister, 2026

import numpy as np
from geometry_msgs.msg import Pose
from moveit_commander.exception import MoveItCommanderException
import json


class FrankaRobot:
    def __init__(self, arm_name, hand_name, moveit_commander, poses_file: str):
        self.arm     = moveit_commander.MoveGroupCommander(arm_name)
        self.gripper = moveit_commander.MoveGroupCommander(hand_name)

        self.arm.set_goal_orientation_tolerance(0.005)
        self.arm.set_goal_position_tolerance(0.005)
        self.set_mode_ptp()

        self._positions = self._load_points(poses_file)

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

    def MoveL(self, name, offset=None):
        self.set_mode_lin()
        self._go_to_point_pose_only(name, offset)

    def MoveJ(self, name, offset=None):
        self.set_mode_ptp()
        self._go_to_point_pose_only(name, offset)

    def MoveJ_J(self, name):
        entry = self._positions.get(name)
        if entry is None:
            raise KeyError(f"Position '{name}' not found.")

        joints = entry["joints"]
        if joints is None:
            raise MoveItCommanderException(f"'{name}' has no joint data.")

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

    def _go_to_point_pose_only(self, name, offset=None):
        entry = self._positions.get(name)
        if entry is None:
            raise KeyError(f"Position '{name}' not found.")

        pose = entry["pose"]

        pose_goal = Pose()
        pose_goal.position.x   = pose.position.x
        pose_goal.position.y   = pose.position.y
        pose_goal.position.z   = pose.position.z
        pose_goal.orientation  = pose.orientation


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

    def gripper_open(self, width: float = 0.04):
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

    def _normalize_quaternion(self, pose):
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

    def _load_points(self, poses_file: str) -> dict:
        positions = {}
        try:
            with open(poses_file, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line.strip())

                    pose = Pose()
                    pose.position.x    = data["pos"][0]
                    pose.position.y    = data["pos"][1]
                    pose.position.z    = data["pos"][2]
                    pose.orientation.x = data["quat"][0]
                    pose.orientation.y = data["quat"][1]
                    pose.orientation.z = data["quat"][2]
                    pose.orientation.w = data["quat"][3]

                    positions[data["name"]] = {
                        "pose":   pose,
                        "joints": data.get("joints")
                    }
        except FileNotFoundError:
            print(f"Poses file not found: {poses_file}")

        return positions
