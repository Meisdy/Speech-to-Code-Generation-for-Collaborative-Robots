"""
Adapter Field Test — tests every BaseRobotController action against a live adapter.

Usage:
    1. Set CONTROLLER and POSES_FILE in the CONFIG section below.
    2. Ensure the robot is powered on, clear of obstacles, and home pose is defined.
    3. Run:  python test_adapter_field.py

Covers every method defined in BaseRobotController. If a method is not supported
by the adapter (e.g. freedrive), it logs INFO rather than failing the test.
"""
import time
from typing import Dict, List, Optional, Tuple

# ── CONFIG — edit before running ──────────────────────────────────────────────
from Backend.robot_controllers.mock_controller import MockRobotController

CONTROLLER_CLASS = MockRobotController
POSES_FILE       = "Backend/data/mock/positions.jsonl"
TEST_POSE_NAME   = "test_position"
SPEED            = 0.3
OFFSET_Z_MM      = 150.0
# ──────────────────────────────────────────────────────────────────────────────

import sys

PASS  = "  ✅ PASS"
FAIL  = "  ❌ FAIL"
INFO  = "  ℹ️  INFO"
SKIP  = "  ⏭️  SKIP"

results: List[Tuple[str, str]] = []


def run(label: str, fn) -> Optional[Dict]:
    """Execute fn(), print result, record pass/fail. Returns response or None on exception."""
    try:
        resp = fn()
        if resp is None:
            print(f"{PASS}  {label}")
            results.append((label, "PASS"))
            return {}
        success = resp.get("success", True)  # Commands with no success key are treated as pass
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
    """Execute fn() — success=False is treated as INFO (feature not supported), not FAIL."""
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

robot = CONTROLLER_CLASS(POSES_FILE)

# ── 1. Connection ──────────────────────────────────────────────────────────────
print("[ Connection ]")
run("connect()", robot.connect)
run("activate_robot()", robot.activate_robot)
run("is_connected()", lambda: {"success": robot.is_connected()})
run("is_ready()", lambda: {"success": robot.is_ready()})

if not robot.is_connected():
    abort("Robot not connected — cannot continue")

# ── 2. Load home pose ──────────────────────────────────────────────────────────
print("\n[ Setup ]")
home = robot.get_pose("home")
if home is None:
    abort("'home' pose not found in poses file — define it before running this test")
print(f"{PASS}  get_pose('home')  →  {home.get('name', home)}")
results.append(("get_pose('home')", "PASS"))

# ── 3. Move to home — safe starting position ───────────────────────────────────
print("\n[ MoveJ ]")
run("move_joint to home",
    lambda: robot.move_joint(home, speed=SPEED))

# ── 4. Current state ───────────────────────────────────────────────────────────
print("\n[ State ]")
state_resp = run("get_current_pose()", robot.get_current_pose)
if state_resp:
    for key in ("joint_positions", "pose", "gripper_state"):
        present = key in state_resp
        tag = PASS if present else FAIL
        print(f"{tag}    get_current_pose has '{key}'")
        results.append((f"get_current_pose.{key}", "PASS" if present else "FAIL"))

# ── 5. MoveJ with offset ───────────────────────────────────────────────────────
print("\n[ MoveJ with offset ]")
offset = [0.0, 0.0, OFFSET_Z_MM]
run(f"move_joint to home + Z {OFFSET_Z_MM}mm",
    lambda: robot.move_joint(home, speed=SPEED, offset=offset))

# ── 6. Teach test pose at current position ─────────────────────────────────────
print("\n[ Pose management ]")
run(f"save_pose('{TEST_POSE_NAME}')",
    lambda: robot.save_pose(TEST_POSE_NAME, overwrite=True))

# ── 7. Back to home before next move ──────────────────────────────────────────
run("move_joint to home",
    lambda: robot.move_joint(home, speed=SPEED))

# ── 8. MoveL to named pose ─────────────────────────────────────────────────────
print("\n[ MoveL ]")
run("move_linear to home",
    lambda: robot.move_linear(home, speed=SPEED))

# ── 9. MoveL with offset ───────────────────────────────────────────────────────
run(f"move_linear to home + Z {OFFSET_Z_MM}mm",
    lambda: robot.move_linear(home, speed=SPEED, offset=offset))

# ── 10. Back to home ───────────────────────────────────────────────────────────
run("move_joint to home",
    lambda: robot.move_joint(home, speed=SPEED))

# ── 11. Move to taught test pose ───────────────────────────────────────────────
print("\n[ Verify taught pose ]")
test_pose = robot.get_pose(TEST_POSE_NAME)
if test_pose is None:
    print(f"{FAIL}  get_pose('{TEST_POSE_NAME}')  →  not found after save")
    results.append((f"get_pose('{TEST_POSE_NAME}')", "FAIL"))
else:
    print(f"{PASS}  get_pose('{TEST_POSE_NAME}')  →  found")
    results.append((f"get_pose('{TEST_POSE_NAME}')", "PASS"))
    run(f"move_joint to {TEST_POSE_NAME}",
        lambda: robot.move_joint(test_pose, speed=SPEED))

# ── 12. Back to home, then delete test pose ────────────────────────────────────
run("move_joint to home",
    lambda: robot.move_joint(home, speed=SPEED))

run(f"delete_pose('{TEST_POSE_NAME}')",
    lambda: robot.delete_pose(TEST_POSE_NAME))

# ── 13. Gripper ────────────────────────────────────────────────────────────────
print("\n[ Gripper ]")
run("gripper_open()",  robot.gripper_open)
run("gripper_close()", robot.gripper_close)

# ── 14. Freedrive (optional — not all adapters support it) ────────────────────
print("\n[ Freedrive ]")
run_optional("enable_freedrive()",  robot.enable_freedrive)
time.sleep(5)
run_optional("disable_freedrive()", robot.disable_freedrive)

# ── 15. Disconnect ─────────────────────────────────────────────────────────────
print("\n[ Disconnection ]")
run("disconnect()", lambda: robot.disconnect() or {"success": True})
run("is_connected() → False",
    lambda: {"success": not robot.is_connected()})

# ── Summary ────────────────────────────────────────────────────────────────────
print_summary()