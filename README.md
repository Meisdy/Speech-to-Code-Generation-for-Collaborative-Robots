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
- **Frontend:** Windows 11, [LM Studio](https://lmstudio.ai) with `meta-llama-3.1-8b-instruct` loaded and served locally
- **Backend (UR / Mock):** Windows 11
- **Backend (Franka):** Ubuntu 20.04 with RT kernel, ROS Noetic, MoveIt — see [Setup/README.md](Setup/README.md)

Launch via the Desktop shortcuts. The mock adapter starts selected in the GUI — no robot or LM Studio required to test the pipeline end-to-end.

---

## Development

See [Setup/README.md](Setup/README.md) for full classic installation instructions covering all robot adapters and operating systems.

### Manual setup for Devs (no installer) in PowerShell.

Requires: Python 3.12, [LM Studio](https://lmstudio.ai) running locally on port 1234 with a model loaded.

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

## Thesis

**Title:** Speech-to-Code Generation for Collaborative Robots
**Author:** Sandy Meister
**Programme:** Master in Robotics and Automation, University West
