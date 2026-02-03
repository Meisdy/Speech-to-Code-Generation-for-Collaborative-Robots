#!/usr/bin/env python3
from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface
import time
from math import pi

"""
RTDE Test Script for UR - Move + Read State

QUICK SETUP CHECKLIST (do BEFORE running):
1. Robot power ON → Installation → Fieldbus → DISABLE Ethernet/IP, Profinet, Modbus → Save.
2. Press Remote/Local button (top-right screen) → Set to REMOTE control.
3. PC Ethernet: Static IP same subnet as robot (e.g. robot 192.168.1.100 → PC 192.168.1.101/255.255.255.0).
5. Edit ROBOT_IP below, run script.

Safety: Start with robot powered down or in safe pose.
"""

# Change to your robot IP
ROBOT_IP = "192.168.0.10"  # e.g., UR5e

rtde_c = RTDEControlInterface(ROBOT_IP)
rtde_r = RTDEReceiveInterface(ROBOT_IP)

# Home position (safe, accessible joint config)
home_joints = [0.0, -pi/2, pi/2, -pi/2, -pi/2, 0.0]

print("Moving to home while reading state...")

# Move to home (blocking call, but we read before/during/after)
print("Before moveJ - q[0]:", rtde_r.getActualQ()[0])
rtde_c.moveJ(home_joints, 0.5, 0.5, 0.5)  # speed, accel, blend
print("After moveJ  - q[0]:", rtde_r.getActualQ()[0])

# Small linear move while reading in a loop
print("\nDoing small moveL while streaming state...")
pose = rtde_r.getActualTCPPose()
target_pose = list(pose)
target_pose[2] += 0.05  # up 5 cm

rtde_c.moveL(target_pose, 0.25, 0.25, 0.25)

# Read continuously during and after move
for i in range(20):  # 20 reads at ~10 Hz
    q = rtde_r.getActualQ()
    tcp = rtde_r.getActualTCPPose()
    print(f"Loop {i}: q[0]={q[0]:.3f}, TCP z={tcp[2]:.3f}")
    time.sleep(0.1)

print("Test complete.")
rtde_c.stopScript()
rtde_c.disconnect()
rtde_r.disconnect()
