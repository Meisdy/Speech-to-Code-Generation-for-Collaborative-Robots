"""
Adapter Field Test — tests every BaseRobotController action against a live adapter.

Usage:
    1. Set CONTROLLER in the CONFIG section below.
    2. Ensure the robot is powered on, clear of obstacles.
    3. Ensure home pose is defined and poses file is hardcoded in the controller.
    4. Run:  python3 -m Testing.adapter_field_test (running as module due to imports from root)

Covers every method defined in BaseRobotController. If a method is not supported
by the adapter (e.g. freedrive), it logs INFO rather than failing the test.
"""
import sys
import time
from typing import Dict, List, Optional, Tuple

# ── CONFIG — edit before running ──────────────────────────────────────────────
from Backend.robot_controllers.ur_controller import URController

CONTROLLER_CLASS = URController
TEST_POSE_NAME   = "test_position"
SPEED            = 0.5
OFFSET           = [250.0, -50, -150.0]   # [x, y, z] in mm
# ──────────────────────────────────────────────────────────────────────────────

PASS = "  ✅ PASS"
FAIL = "  ❌ FAIL"
INFO = "  ℹ️  INFO"

results: List[Tuple[str, str]] = []


def run(label: str, fn) -> Optional[Dict]:
    try:
        resp = fn()
        if resp is None:
            print(f"{PASS}  {label}")
            results.append((label, "PASS"))
            return {}
        success = resp.get("success", True)
        tag = PASS if success else FAIL
        msg = resp.get("message", "")
        print(f"{tag}  {label}{f'  →  {msg}' if msg else ''}")
        results.append((label, "PASS" if success else "FAIL"))
        return resp
    except Exception as e:
        print(f"{FAIL}  {label}  →  Exception: {e}")
        results.append((label, "FAIL"))
        return None


def run_optional(label: str, fn) -> None:
    try:
        resp = fn()
        if resp is None or resp.get("success", True):
            print(f"{PASS}  {label}")
            results.append((label, "PASS"))
        else:
            print(f"{INFO}  {label}  →  {resp.get('message', 'Not supported')}")
            results.append((label, "INFO"))
    except Exception as e:
        print(f"{FAIL}  {label}  →  Exception: {e}")
        results.append((label, "FAIL"))


def abort(reason: str) -> None:
    print(f"\n🛑  ABORTED: {reason}")
    sys.exit(1)


def print_summary() -> None:
    total  = len(results)
    passed = sum(1 for _, s in results if s == "PASS")
    failed = sum(1 for _, s in results if s == "FAIL")
    info   = sum(1 for _, s in results if s == "INFO")
    print("\n" + "─" * 60)
    print(f"  Results: {passed}/{total} passed   {failed} failed   {info} info")
    if failed:
        print("\n  Failed steps:")
        for label, status in results:
            if status == "FAIL":
                print(f"    • {label}")
    print("─" * 60)


# ── Test sequence ──────────────────────────────────────────────────────────────

print(f"\n{'─' * 60}")
print(f"  Adapter Field Test — {CONTROLLER_CLASS.__name__}")
print(f"{'─' * 60}\n")

robot = CONTROLLER_CLASS()

# ── 1. Connection ──────────────────────────────────────────────────────────────
print("[ Connection ]")
run("connect()",       robot.connect)
run("activate_robot()", robot.activate_robot)
run("is_connected()",  lambda: {"success": robot.is_connected()})
run("is_ready()",      lambda: {"success": robot.is_ready()})

if not robot.is_connected():
    abort("Robot not connected — cannot continue")

home_pose = robot.get_pose("home")
if home_pose is None:
    abort("'home' pose not found — define it before running this test")

# ── 2. Current state ───────────────────────────────────────────────────────────
print("\n[ State ]")
state_resp = run("get_current_pose()", robot.get_current_pose)
if state_resp:
    for key in ("joint_positions", "pose", "gripper_state"):
        present = key in state_resp
        print(f"{'  ✅ PASS' if present else '  ❌ FAIL'}    get_current_pose has '{key}'")
        results.append((f"get_current_pose.{key}", "PASS" if present else "FAIL"))

# ── 3. MoveJ ──────────────────────────────────────────────────────────────────
print("\n[ MoveJ ]")
run("move_joint  — named pose 'home'",
    lambda: robot.move_joint(home_pose, speed=SPEED))
run("move_joint  — named pose 'home' + offset",
    lambda: robot.move_joint(home_pose, speed=SPEED, offset=OFFSET))

# ── 4. MoveL ──────────────────────────────────────────────────────────────────
print("\n[ MoveL ]")
run("move_linear — named pose 'home'",
    lambda: robot.move_linear(home_pose, speed=SPEED))
run("move_linear — named pose 'home' + offset",
    lambda: robot.move_linear(home_pose, speed=SPEED, offset=OFFSET))

# ── 5. Pose management ────────────────────────────────────────────────────────
print("\n[ Pose management ]")
run(f"save_pose('{TEST_POSE_NAME}')",
    lambda: robot.save_pose(TEST_POSE_NAME, overwrite=True))

test_pose = robot.get_pose(TEST_POSE_NAME)
if test_pose is None:
    print(f"{FAIL}  get_pose('{TEST_POSE_NAME}')  →  not found after save")
    results.append((f"get_pose('{TEST_POSE_NAME}')", "FAIL"))
else:
    print(f"{PASS}  get_pose('{TEST_POSE_NAME}')  →  found")
    results.append((f"get_pose('{TEST_POSE_NAME}')", "PASS"))
    robot.move_joint(home_pose, speed=SPEED) # go to home first
    run(f"move_joint  — taught pose '{TEST_POSE_NAME}'",
        lambda: robot.move_joint(test_pose, speed=SPEED))

run(f"delete_pose('{TEST_POSE_NAME}')",
    lambda: robot.delete_pose(TEST_POSE_NAME))

robot.move_joint(home_pose, speed=SPEED) # go to home again


# ── 6. Gripper ────────────────────────────────────────────────────────────────
print("\n[ Gripper ]")
run("gripper_open()",  robot.gripper_open)
run("gripper_close()", robot.gripper_close)

# ── 7. Freedrive (optional) ───────────────────────────────────────────────────
print("\n[ Freedrive ]")
run_optional("enable_freedrive()",  robot.enable_freedrive)
time.sleep(5)
run_optional("disable_freedrive()", robot.disable_freedrive)

# ── 8. Disconnect ─────────────────────────────────────────────────────────────
print("\n[ Disconnection ]")
run("disconnect()",        lambda: robot.disconnect() or {"success": True})
run("is_connected() → False", lambda: {"success": not robot.is_connected()})

# ── Summary ───────────────────────────────────────────────────────────────────
print_summary()