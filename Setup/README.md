# Setup Guide — Speech-to-Code Generation for Collaborative Robots

The system consists of a **frontend** (operator machine) and a **backend** (machine connected to the robot). Both must be running simultaneously.

| Component                               | Machine | OS |
|-----------------------------------------|---|---|
| Frontend — GUI                          | Operator machine | Windows 11 |
| Backend — Mock / Universal Robots UR10e | Same machine as frontend, or a separate Windows PC | Windows 11 |
| Backend — Franka Emika Panda            | Dedicated Linux PC | Ubuntu 20.04 (RT kernel) |

Frontend and backend communicate over ZeroMQ on port `5555`. For Franka, the Linux PC must be reachable from the operator machine on the network.

---

## Quick Start

> **This Quick Start covers Mock and UR setups only.** For Franka, follow the dedicated installation and session preparation sections below.

1. Install [LM Studio](https://lmstudio.ai). Load `meta-llama-3.1-8b-instruct` and serve on port `1234`.
2. Install the frontend:
   ```powershell
   irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_frontend.ps1 | iex
   ```
3. Install the backend:
   ```powershell
   irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_backend.ps1 | iex
   ```
4. Launch frontend and backend from their Desktop shortcuts.

> **Note:** The mock adapter requires no robot hardware, but LM Studio must still be running for LLM parsing.

---

## Frontend Installation (Windows 11)

### Prerequisites

LM Studio must be running before the application starts:
1. Download from [lmstudio.ai](https://lmstudio.ai)
2. Load `meta-llama-3.1-8b-instruct`
3. Start the local server on port `1234`

### Install
Use PowerShell as administrator to run the setup script:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_frontend.ps1 | iex
```

The script installs `ffmpeg` and `uv` via winget if missing, downloads the application to `C:\Program Files\Speech-to-Cobot`, creates a Desktop shortcut, and pre-downloads the Whisper small model (~466 MB). Full script details in [setup_frontend.ps1](https://github.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/blob/main/Setup/setup_frontend.ps1)

To uninstall, see [Uninstall](#uninstall).

---

## Backend Installation — Windows (Mock / UR)

Use PowerShell as administrator to run the setup script:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_backend.ps1 | iex
```

Installs `uv` via winget if missing, downloads to `C:\Program Files\Speech-to-Cobot-Backend`, creates a Desktop shortcut. Full script details in [setup_backend.ps1](https://github.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/blob/main/Setup/setup_backend.ps1)

Before running with a real UR robot, see [Before Each Session](#before-each-session--robot-preparation) for robot preparation steps and [Network Setup](#network-setup) for IP configuration.

---

## Backend Installation — Linux (Franka)

**This setup is time-consuming and not recommended as a first test.** It uses an older robot and a full Linux FCI stack that must be configured manually.

The Franka adapter requires a dedicated Linux PC with a real-time kernel. This cannot be automated — the ROS stack must be set up manually first.

### Prerequisites

- Ubuntu 20.04 with PREEMPT_RT real-time kernel
- ROS Noetic
- MoveIt (`panda_moveit_config`, `franka_control`)
- libfranka (compatible with your robot firmware)
- A working MoveIt workspace at `~/ws_moveit`

See the official docs: [ROS Noetic](https://wiki.ros.org/noetic/Installation/Ubuntu), [MoveIt](https://moveit.ros.org/install), [libfranka](https://github.com/frankarobotics/libfranka).

Ensure the backend source code is on the Linux PC before launching.

### Launch Command

```bash
python3 -m Backend.main
```

The backend connects to the robot at `192.168.1.100` by default. Verify `ROBOT_IP` in `Backend/robot_controllers/franka_controller.py` before launching.

---

## Before Each Session — Robot Preparation

These steps are required before every session, separate from the one-time software installation above.

### UR10e

1. Power on the UR10e via the Teach Pendant Start Button.
2. Set the robot mode from **Local** to **Remote Mode** via Teach Pendant.
3. Plug in the Ethernet cable between the robot and the backend machine.
4. *(First-time only)* Ensure the backend machine and robot are on the same network and IPs are configured — see [Network Setup](#network-setup).
5. Launch frontend and backend from their Desktop shortcuts. Use **Ping Backend** in the GUI to test the backend connection.

> **Always use Remote Mode.** In Local Mode, motion commands are silently ignored — the robot accepts them but does not move. Gripper and save-position still work, which can make the root cause difficult to identify.

### Franka

1. Turn on the Franka controller.
2. Start the Linux desktop PC, selecting the RT kernel at boot.
3. *(First-time only)* Configure the network adapters on the Linux PC — one toward the robot, one toward the operator machine. Follow the [Franka documentation](https://frankarobotics.github.io/libfranka) for initial network setup.
4. Check that the network adapters are active and plug in the Ethernet cable between the Linux PC and the operator machine. Run a test ping to confirm the connection.
5. Open the Franka Desk in a browser at `https://<franka-robot-ip>`. Accept the self-signed certificate warning — all browsers will show this.
6. In Desk: unlock the axes.
7. Engage the hand switch on the arm once, then release it.
8. Enable FCI in Desk.
9. Start the backend on the Linux PC:
   ```bash
   python3 -m Backend.main
   ```
10. Start the frontend on the operator machine. The backend must be reachable before any commands can be sent.

> **The Franka must show blue (Ready)** before issuing motion commands. In hand-guide mode (white), commands are accepted but not executed.

---

## Network Setup

The setup below describes the configuration used during development and evaluation: a direct Ethernet connection between the operator machine and the robot or backend PC. Using a router or switch is also possible if available, but was not tested.

### Direct Ethernet (no router)

1. Find the robot IP. Consult your robot's interface or documentation to locate the current IP address.
2. On the backend machine, set a static IP on the **Ethernet adapter connected to the robot** to the same subnet as the robot. On Windows 11: Settings → Network & Internet → Advanced network settings → select the correct adapter → Edit → Manual → IPv4. No gateway needed. This setting persists per adapter.
3. Verify that the robot IP in `Backend/robot_controllers/<your_robot_controller>.py` matches the actual robot IP.
4. If the frontend and backend run on **different machines**, both need to be on the same network. Configure a static IP on each machine's Ethernet adapter facing the other (same process as step 2). Then update `BACKEND_IPS` in `Frontend/config_frontend.py` with the backend machine's IP. If both run on the **same machine**, `localhost` is correct and no network configuration is needed.

`Frontend/config_frontend.py` backend address reference:

```python
BACKEND_IPS = {
    "franka": "tcp://192.168.2.20:5555",
    "ur":     "tcp://localhost:5555",
    "mock":   "tcp://localhost:5555",
}
```

Use **Ping Backend** in the GUI to verify. A green indicator confirms the connection immediately. If it does not turn green, check that the backend is running, IPs are correct, and port `5555` is not blocked by a firewall.

---

## Configuration Reference

**Frontend — `Frontend/config_frontend.py`**

| Parameter | Default | Description |
|---|---|---|
| `ASR_MODEL_SIZE` | `small` | Whisper model: `tiny`, `base`, `small`, `medium`, `large` |
| `LLM_API_BASE` | `http://localhost:1234/v1` | LM Studio server URL |
| `LLM_MODEL_NAME` | — | Model name as shown in LM Studio |
| `BACKEND_IPS` | — | ZeroMQ addresses per robot backend |
| `ROBOT_TYPE_KEYS` | — | Maps GUI display names to backend robot types |
| `MAX_ATTEMPTS` | `2` | Retry attempts when backend is unreachable |
| `ASR_LANGUAGE` | `en` | ISO language code for ASR |
| `ASR_SAMPLE_RATE` | `16000` | Audio sample rate in Hz |
| `ASR_CONFIDENCE_THRESHOLD` | — | Warn on transcripts below this threshold (0.0–1.0) |
| `LOGGING_LEVEL` | `INFO` | Console log verbosity |
| `LOGGING_LEVEL_FILE` | — | File log verbosity (can differ from console) |
| `LOGGING_SAVE_AUDIO` | `False` | Save microphone input as `.wav` for debugging |
| `LOGGING_SAVE_PARSE` | `False` | Save parsed JSON for parser debugging |

**Backend — `Backend/config_backend.py`**

| Parameter | Default | Description |
|---|---|---|
| `BINDING_ADDRESS` | `tcp://*:5555` | ZeroMQ binding address |
| `ZMQ_TIMEOUT_MS` | `1000` | ZeroMQ socket timeout |
| `AVAILABLE_ROBOTS` | `mock, ur, franka` | Adapters to load |
| `PC_IP` | — | Backend machine IP as seen by the UR robot (UR motion callback only) |
| `LOGGING_LEVEL` | `INFO` | Console log verbosity |
| `LOGGING_LEVEL_FILE` | — | File log verbosity |

---

## Uninstall

### Frontend (Windows)

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/uninstall_frontend.ps1 | iex
```

Removes the installation directory, Desktop shortcut, and Whisper cache. Prompts optionally remove `ffmpeg` and `uv`. LM Studio must be uninstalled manually via **Settings → Apps**.

### Backend (Windows)

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/uninstall_backend.ps1 | iex
```