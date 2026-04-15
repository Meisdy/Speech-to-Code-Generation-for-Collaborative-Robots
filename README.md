# Speech-to-Code Generation for Collaborative Robots

Software repository for the master's thesis *Speech-to-Code Generation for Collaborative Robots — A Modular Framework for Multi-Vendor Robot Programming in Structured Workspaces* at University West, Department of Engineering Science.

---

## What this is

A modular pipeline that lets users program collaborative robots through spoken commands. The user speaks a command, the system transcribes it, passes it to a local LLM, generates structured robot control code, and executes it on the connected robot — all in real time.

The framework supports multiple robot backends through a swappable adapter architecture. Currently implemented: Franka Emika Panda, Universal Robots UR10e, and a mock adapter for testing without hardware. To add a new robot, simply implement the adapter interface and register it — no changes needed to the frontend or LLM prompts.

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


**Requirements:**
- **Frontend:** Windows 11, [LM Studio](https://lmstudio.ai) with `meta-llama-3.1-8b-instruct` loaded and served on port `1234`
- **Backend (Universal Robot UR10e / Mock):** Windows 11
- **Backend (Franka Emika Panda):** No installer — see [Setup/README.md](Setup/README.md) for manual setup

For full setup instructions and uninstallers, see **[Setup/README.md](Setup/README.md)**.

The one-line installers set up everything and create Desktop shortcuts. Requires PowerShell running as Administrator.

**Before launching:** LM Studio must already be running with a model loaded and the local server started on port `1234`.

```powershell
# Frontend
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_frontend.ps1 | iex

# Backend
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_backend.ps1 | iex
```

---

## Available Commands

Voice commands are parsed by the LLM into structured JSON. Defaults (motion type, units, wait time) are defined in `Frontend/ruleset.json` — they apply automatically unless overridden.

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

| Command         | Description                        |
|-----------------|------------------------------------|
| `script start`  | Begin recording a command sequence |
| `script save`   | End recording and save the script  |
| `script run`    | Execute a saved script N times     |
| `script stop`   | Cancel script recording mode       |
| `script delete` | Delete a saved script              |

When a script is running and needs to be stopped, this can be done with a dedicated Stop button in the GUI.

---

## Command Details

### `move`

Three target types — the LLM selects the correct one based on your phrasing:

- **Named pose** — "move to home", "go to P1"
- **Offset from pose** — "move 50mm right from home", "go to P1 offset x=80 y=50"
- **Offset from current** — "move up 100mm", "shift left 30mm"

Default motion type is `moveJ` (joint-space). Say "linearly" or "in a straight line" or similar to get `moveL`.

### `gripper`

Say "open" or "close" — the word must be present. Phrases like "make gripper" or just "gripper" with no state word are instructed to produce no action.

### `freedrive`

Hand-guiding mode, if implemented on the robot adapter. The word "freedrive" must be present **and** one of these state words: "on", "off", "enable", "disable". If no state word is detected, the command should get rejected rather than inferred.

Examples that work: "enable freedrive", "freedrive on", "turn off freedrive"  

### `pose`

Teach a pose by moving the robot manually, or using commands like move down 20mm, then saying "teach pose P1" or "save position home". Poses are stored persistently in a JSONL file and survive restarts. Use "delete pose P1" to remove one.

### `script`

Record a sequence of commands as a named script for replay. Trigger script recording with "start new script" or "start new script called dance". Issue commands as you normally would. Commands get saved and are not being executed. When done, use "save script" or similar to save it. A confirmation window appears, which also lets you fix broken lines, and then confirm or cancel the save operation. To run it, say "execute script called dance 5x" or similar. Allows infinite looping with words like "loop forever". Scripts are stored in a JSONL file alongside poses.

---

## Configuration

All settings are in plain-text config files — no reinstallation needed to change them. Just use your favorite text editor.

| File | What it controls |
|---|---|
| `Frontend/config_frontend.py` | ASR model, LLM connection, backend IPs, logging |
| `Backend/config_backend.py` | ZeroMQ binding, robot adapters, UR callback IP |
| `Frontend/ruleset.json` | Default motion type, units, wait time, command structure |
| `Frontend/prompts/system_prompt.txt` | LLM parsing rules — edit to change how commands are interpreted |

Defaults reference: [Setup/README.md#configuration-reference](Setup/README.md#configuration-reference)

---

## Debugging

**Log files** are written to `Backend/logs/` and `Frontend/logs/` when running from source. The installed version writes to `$INSTALL_DIR\Backend\logs` and `$INSTALL_DIR\Frontend\logs`.

**Save microphone input** for ASR debugging:
```python
LOGGING_SAVE_AUDIO = True  # in config_frontend.py
```

**Save parsed JSON** for parser debugging:
```python
LOGGING_SAVE_PARSE = True  # in config_frontend.py
```

Audio and parse files are saved to `Frontend/data/`.

---

## Adding a new robot adapter

The adapter translates high-level commands into robot-specific communication. Once registered, the backend dispatches commands to it automatically — no other code changes are needed.

1. Backend: create `Backend/robot_controllers/<robot>_controller.py` inheriting from `BaseRobotController`. Implement the abstract methods — see `BaseRobotController` docstrings for signatures and expected behavior. `ur_controller.py` is the reference for real robot integration; `mock_controller.py` is useful for testing without hardware.
2. Backend: add `<robot>` to `AVAILABLE_ROBOTS` in `Backend/config_backend.py`.
3. Frontend: add `<robot>` to `ROBOT_TYPE_KEYS` in `Frontend/config_frontend.py` — this adds it to the robot selection dropdown.

---

## Development

### Manual setup

Requires Python 3.12 and LM Studio running on port `1234`. First frontend startup will download Whisper model either in background or teminal. 
Obviously, one can install it without a venv aswell. 

```powershell
git clone https://github.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots
cd "Speech-to-Code-Generation-for-Collaborative-Robots"

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r Setup/requirements_frontend.txt
pip install -r Setup/requirements_backend.txt
```

### Running

```powershell
# Terminal 1 — backend
python -m Backend.main

# Terminal 2 — frontend
python -m Frontend.main
```

`Testing/` contains integration tests and evaluation protocols used during development.

---

## Ideas for Extensions

A few directions this framework could be taken further:

- **Cloud LLM support** — replace the local LM Studio backend with a cloud API for faster or more capable parsing
- **More Robust Parsing** — implement a feedback loop where the LLM can ask clarifying questions if the command is ambiguous or incomplete. Further prompt engineering to handle more complex commands and edge cases, as well as to counter hallucinations and parsing errors.
- **Configurable motion speed** — expose speed as a user-settable parameter rather than a hardcoded value in the adapter
- **Support for Zone commands** — allow users to specify approach and departure zones for linear motions, with configurable sizes
- **Web dashboard** — replace or extend the desktop GUI with a browser-based interface for remote monitoring and control

---

## Thesis

**Title:** Speech-to-Code Generation for Collaborative Robots  
**Author:** Sandy Meister  
**Programme:** Master in Robotics and Automation, University West
