# Speech-to-Code Generation for Collaborative Robots

Software repository for the master's thesis *Speech-to-Code Generation for Collaborative Robots — A Modular Framework for Multi-Vendor Robot Programming in Structured Workspaces* at University West, Department of Engineering Science.

---

## What this is

A modular pipeline that lets users program collaborative robots through spoken commands. The user speaks a command, the system transcribes it, passes it to a local LLM, generates structured robot control code, and executes it on the connected robot — all in real time.

The framework supports multiple robot backends through a swappable adapter architecture. Currently implemented: Franka Emika Panda, Universal Robots UR10e, and a mock adapter for testing without hardware.

---

## Repository structure

```
├── Frontend/        — GUI, ASR module, LLM parser, ZeroMQ client
├── Backend/         — ZeroMQ server, message handler, robot adapters
├── Testing/         — Integration tests, field test scripts, evaluation protocol
└── Setup/           — Installer and uninstaller scripts, setup guide
```

---

## Quick installation

The one-line installer sets up everything and creates a Desktop shortcut. Requires PowerShell running as Administrator.

```powershell
# Frontend
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_frontend.ps1 | iex

# Backend
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_backend.ps1 | iex
```

**Requirements:**
- **Frontend:** Windows 11, [LM Studio](https://lmstudio.ai) with `meta-llama-3.1-8b-instruct` loaded and served locally — required for all adapters including mock
- **Backend (UR / Mock):** Windows 11
- **Backend (Franka):** No installer available — see [Setup/README.md](Setup/README.md) for manual setup

Launch via the Desktop shortcuts. For full setup instructions covering all robot adapters, see **[Setup/README.md](Setup/README.md)**.

---

## Development

### Manual setup for Devs (no installer) in PowerShell.

Requires: Python 3.12, [LM Studio](https://lmstudio.ai) running locally on port 1234 with a model loaded.
Make sure you are in the directory where you want to clone the repo before running these commands.

```powershell
# Clone the repo
git clone https://github.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots
cd "Speech-to-Code-Generation-for-Collaborative-Robots"

# Create and activate virtual environment
python -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force # Allow running local scripts
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r Setup/requirements_frontend.txt
pip install -r Setup/requirements_backend.txt

# Start backend (Mock adapter — no hardware)
python -m Backend.main

# In a new terminal, start frontend
python -m Frontend.main
```

### Testing

Tests live in `Testing/`. Run them in your IDE or with `pytest` — the backend must be running on `tcp://localhost:5555` first.

### Adding a new robot adapter

The adapter translates high-level commands (move, gripper, etc.) into robot-specific communication. Once registered, the backend dispatches commands to it automatically — no other code changes are needed.

1. Backend: create `Backend/robot_controllers/<robot>_controller.py` inheriting from `BaseRobotController`. Implement the abstract methods — see `BaseRobotController` docstrings for signatures and expected behavior. `URController` serves as a complete reference implementation.
2. Backend: add `<robot>` to `AVAILABLE_ROBOTS` in `Backend/config_backend.py`.
3. Frontend: add `<robot>` to `ROBOT_TYPE_KEYS` in `Frontend/config_frontend.py` — this adds it to the robot selection dropdown.

---

## Available Commands

Voice commands are parsed by the LLM into structured robot actions. Defaults (motion type, units, wait time) are defined in `Frontend/ruleset.json` — they apply automatically unless overridden.

### Robot Actions

| Command | Description |
|---|---|
| `move` | Move to a named pose, or offset from a pose or current position |
| `gripper` | Open or close the gripper |
| `wait` | Pause execution for a given duration |
| `pose` | Teach (save) or delete a named pose |
| `freedrive` | Enable or disable hand-guiding mode |
| `connection` | Connect or disconnect from the robot |

### Script Recording & Replay

| Command | Description |
|---|---|
| `script start` | Begin recording a command sequence |
| `script save` | End recording and save the script |
| `script run` | Execute a saved script |
| `script stop` | Stop execution or cancel recording |
| `script delete` | Delete a saved script |

---

## Thesis

**Title:** Speech-to-Code Generation for Collaborative Robots
**Author:** Sandy Meister
**Programme:** Master in Robotics and Automation, University West