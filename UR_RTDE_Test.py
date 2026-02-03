#!/usr/bin/env python3
from rtde_control import RTDEControlInterface
from rtde_receive import RTDEReceiveInterface
from math import pi
from scipy.spatial.transform import Rotation
import json
from pathlib import Path

"""
RTDE Test Script for UR - Move + Read State + Teach

QUICK SETUP CHECKLIST (do BEFORE running):
1. Robot power ON → Installation → Fieldbus → DISABLE Ethernet/IP, Profinet, Modbus → Save.
2. Press Remote/Local button (top-right screen) → Set to REMOTE control.
3. PC Ethernet: Static IP same subnet as robot (e.g. robot 192.168.1.100 → PC 192.168.1.101/255.255.255.0).
5. Edit ROBOT_IP below, run script.

Safety: Start with robot powered down or in safe pose.
"""

# Change to your robot IP
ROBOT_IP = "169.254.70.80"  # e.g., UR5e
POSITIONS_FILE = "positions.jsonl"

rtde_c = RTDEControlInterface(ROBOT_IP)
rtde_r = RTDEReceiveInterface(ROBOT_IP)


# ========== TEACH POSITION FUNCTION ==========
def teach_position(pose_name, overwrite=False):
    """
    Capture current robot pose and save to positions.jsonl

    Args:
        pose_name: Name for this position (e.g. "P1", "HomeTest")
        overwrite: If True, replace existing position with same name

    Returns:
        "SUCCESS" or "REJECTED"
    """
    # Read current state
    tcp_pose = rtde_r.getActualTCPPose()  # [x,y,z,rx,ry,rz]
    joints = rtde_r.getActualQ()  # 6 joints for UR

    # Convert axis-angle to quaternion
    quat = Rotation.from_rotvec(tcp_pose[3:]).as_quat()  # [qx, qy, qz, qw]

    # Create entry in standard format
    entry = {
        "name": pose_name,
        "pos": list(tcp_pose[:3]),  # [x, y, z] in meters
        "quat": list(quat),  # [qx, qy, qz, qw]
        "joints": list(joints)  # 6 joints for UR
    }

    # Load existing positions
    positions = []
    if Path(POSITIONS_FILE).exists():
        with open(POSITIONS_FILE, 'r') as f:
            for line in f:
                positions.append(json.loads(line.strip()))

    # Check if name exists
    existing_idx = None
    for idx, pos in enumerate(positions):
        if pos["name"] == pose_name:
            existing_idx = idx
            break

    if existing_idx is not None:
        if not overwrite:
            print(f"REJECTED: Position '{pose_name}' already exists (use overwrite=True to replace)")
            return "REJECTED"
        else:
            positions[existing_idx] = entry
            print(f"Overwriting position '{pose_name}'")
    else:
        positions.append(entry)
        print(f"Teaching new position '{pose_name}'")

    # Save to file (write all positions)
    with open(POSITIONS_FILE, 'w') as f:
        for pos in positions:
            f.write(json.dumps(pos) + '\n')

    print(f"Position saved: {pose_name}")
    print(f"  pos: {entry['pos']}")
    print(f"  quat: {entry['quat']}")
    print(f"  joints: {entry['joints']}")

    return "SUCCESS"


# ========== LOAD POSITION FUNCTION ==========
def load_position(pose_name):
    """
    Load a position from positions.jsonl

    Returns:
        dict with pos, quat, joints or None if not found
    """
    if not Path(POSITIONS_FILE).exists():
        print(f"REJECTED: File {POSITIONS_FILE} does not exist")
        return None

    with open(POSITIONS_FILE, 'r') as f:
        for line in f:
            pos = json.loads(line.strip())
            if pos["name"] == pose_name:
                return pos

    print(f"REJECTED: Position '{pose_name}' not found")
    return None


# ========== MAIN TEST SCRIPT ==========

# Read current joints once
current_q = rtde_r.getActualQ()
print("Current joints:", current_q)

# Define home positions
home_joints = [pi, -pi / 2, pi / 2, -pi / 2, -pi / 2, -2.7]
pos2 = [3.141627550125122, -1.8115416965880335, 0.8977630774127405, -2.1082149944701136,
        -1.5707643667804163, -2.700108830128805]

print("Moving to nearby home config...")
rtde_c.moveJ(home_joints, 1, 2)

# ========== TEACH CURRENT POSITION AS "HOME" ==========
print("\n--- Teaching current position as 'Home' ---")
teach_position("Home", overwrite=True)

print('\nStarting dance moves...')
for i in range(1):
    rtde_c.moveJ(pos2, 1, 2)
    rtde_c.moveJ(home_joints, 1, 2)

# ========== TEACH POSITION AFTER DANCE ==========
print("\n--- Teaching current position as 'AfterDance' ---")
teach_position("AfterDance", overwrite=True)

# --- NEW: Linear move (+5cm X, +5cm Y) ---
print("\nDoing linear move (-10cm X, -10cm Y)...")

# 1. Get current Cartesian pose [x, y, z, rx, ry, rz]
current_pose = rtde_r.getActualTCPPose()

# 2. Create target pose
target_pose = list(current_pose)
target_pose[0] -= 0.10  # Subtract 10 cm from X
target_pose[1] -= 0.10  # Subtract 10 cm from Y
print("Target pose:", target_pose)

# 3. Execute linear move (speed 0.25 m/s, accel 0.5 m/s^2)
rtde_c.moveL(target_pose, 0.25, 0.5)

# ========== TEACH POSITION AFTER LINEAR MOVE ==========
print("\n--- Teaching current position as 'P1' ---")
teach_position("P1", overwrite=True)

# ========== LOAD AND MOVE TO SAVED POSITION ==========
print("\n--- Loading and moving back to 'Home' ---")
home_pos = load_position("Home")
if home_pos:
    print(f"Moving to saved Home position using joints...")
    rtde_c.moveJ(home_pos["joints"], 1.0, 1.4)

print("\nTest complete.")
print(f"Saved positions are in: {POSITIONS_FILE}")

rtde_c.stopScript()
rtde_c.disconnect()
rtde_r.disconnect()
