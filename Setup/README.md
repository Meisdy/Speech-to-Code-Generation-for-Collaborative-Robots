# Setup Guide
## Speech-to-Code Generation for Collaborative Robots

This guide covers installation of the full system. The system has two components that run as separate processes — the **frontend** (operator machine) and the **backend** (machine connected to the robot). Both must be running for the system to function.

---

## System Overview

| Component | Machine | OS |
|---|---|---|
| Frontend | Operator machine | Windows 11 |
| Backend — Windows installer | Any Windows machine | Windows 11 |
| Backend — Franka Emika | Dedicated Linux PC | Ubuntu 20.04 (RT kernel) |

The Windows backend installer supports all adapters that do not require a Linux environment — currently Mock and Universal Robots. The Franka adapter requires a dedicated Linux setup described in Part 3.

The frontend and backend communicate over a local network via ZeroMQ. The backend machine must be reachable from the frontend machine on port `5555`.

---

## Part 1 — Frontend (Windows 11)

### Prerequisites

LM Studio must be installed and configured manually before the application will function:

1. Download from [lmstudio.ai](https://lmstudio.ai)
2. Load model: `meta-llama-3.1-8b-instruct`
3. Start the local server on port `1234` before launching the application

### Install

Open PowerShell as Administrator (right-click → *Run as Administrator*) and run:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/setup_frontend.ps1 | iex
```

The script installs `ffmpeg` and `uv` via winget if not present, downloads the frontend to `C:\Program Files\Speech-to-Cobot`, creates a Desktop shortcut, and pre-downloads the Whisper base model (~140 MB).

### Launch

Double-click **Speech-to-Cobot** on the Desktop.

### Uninstall

Run the following in Administrator PowerShell, or run `uninstall_frontend.ps1` directly from the install directory if internet is not available:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/uninstall_frontend.ps1 | iex
```

Removes the install directory, Desktop shortcut, and Whisper model cache. Optionally removes `ffmpeg` and `uv` — you will be prompted for each. LM Studio must be removed manually via **Settings → Apps**.

---

## Part 2 — Backend: Windows Installer

This installer supports all robot adapters that run on Windows — currently **Mock** (no hardware required) and **Universal Robots**. The Franka adapter is not supported on Windows and requires the separate Linux setup described in Part 3.

### Install

Open PowerShell as Administrator and run:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/setup_backend.ps1 | iex
```

The script installs `uv` via winget if not present, downloads the backend to `C:\Program Files\Speech-to-Cobot-Backend`, and creates a Desktop shortcut.

### Launch

Double-click **Speech-to-Cobot Backend** on the Desktop. A terminal window opens showing server logs. Keep this window open while the frontend is running. Press `Ctrl+C` to stop the server.

### Configuration

Before running with a real UR robot, verify the following in `Backend\config_backend.py`:

- `BINDING_ADDRESS` — ZeroMQ binding address (default: `tcp://*:5555`)
- `PC_IP` — IP address of the backend machine as seen by the UR robot (required for motion callback)

The robot IP is configured in the UR controller at `Backend\robot_controllers\ur_controller.py` (`DEFAULT_ROBOT_IP`).

### Uninstall

Run the following in Administrator PowerShell, or run `uninstall_backend.ps1` directly from the install directory if internet is not available:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/uninstall_backend.ps1 | iex
```

---

## Part 3 — Backend: Franka Emika (Linux)

The Franka backend runs on a dedicated Linux PC with a real-time kernel. This setup cannot be automated — the machine requires manual configuration of the full ROS stack before the backend can run.

### Prerequisites

The following must be installed and configured on the Linux PC before proceeding:

- Ubuntu 20.04 with PREEMPT_RT real-time kernel
- ROS Noetic
- MoveIt (`panda_moveit_config`, `franka_control`)
- libfranka (compatible version for your robot firmware)
- A working MoveIt workspace at `~/ws_moveit`

Refer to the official documentation for each:
- [ROS Noetic installation](https://wiki.ros.org/noetic/Installation/Ubuntu)
- [MoveIt setup for Franka](https://moveit.ros.org/install)
- [libfranka installation](https://github.com/frankarobotics/libfranka)

### Backend installation

Once the ROS stack is confirmed working, install the backend Python dependencies into the ROS Python environment:

```bash
pip install pyzmq numpy scipy
```

Download or clone the repository and navigate to the repo root:

```bash
cd ~/path/to/repo
```

### Launch

Start the backend server:

```bash
python -m Backend.main
```

The backend connects to the robot at `192.168.1.100` by default. Verify the robot IP in `Backend/robot_controllers/franka_controller.py` (`ROBOT_IP`) and the backend machine IP in `Backend/config_backend.py` (`PC_IP`).

---

## Configuration Files

Both components have a single configuration file that covers all runtime parameters. These are the only files that typically need to be edited when deploying to a different environment.

**Frontend — `Frontend/config_frontend.py`**

| Parameter | Description |
|---|---|
| `FRAMEWORK_MODE` | `live` for real execution, other modes for testing |
| `ASR_MODEL_SIZE` | Whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
| `LLM_API_BASE` | LM Studio server URL (default: `http://localhost:1234/v1`) |
| `LLM_MODEL_NAME` | Model name as shown in LM Studio |
| `BACKEND_IPS` | ZeroMQ addresses for each robot backend |
| `LOGGING_LEVEL` | Console log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOGGING_SAVE_AUDIO` | Save microphone input as `.wav` for debugging |
| `LOGGING_SAVE_PARSE` | Save LLM output as `.json` for debugging |

**Backend — `Backend/config_backend.py`**

| Parameter | Description |
|---|---|
| `BINDING_ADDRESS` | ZeroMQ binding address (default: `tcp://*:5555`) |
| `AVAILABLE_ROBOTS` | List of adapters to load: `mock`, `ur`, `franka` |
| `PC_IP` | IP of the backend machine as seen by the UR robot (required for motion callback) |
| `LOGGING_LEVEL` | Console log verbosity |



The frontend connects to the backend via ZeroMQ on port `5555`. How you configure the network depends on your physical setup.

**Via router or switch:** assign static IPs to all devices on the same subnet, or use DHCP and update `config_frontend.py` with the correct backend IP. No adapter configuration is needed beyond a normal network connection.

**Direct Ethernet connection (no router):** the connecting adapter on the operator machine must be set to a static IP on the same subnet as the target device. On Windows 11: Settings → Network & Internet → Advanced network settings → select the adapter → Edit → Manual → IPv4, set IP and subnet mask (`255.255.255.0`), no gateway. Windows saves this per adapter, so it persists for that cable or dongle.

Once the network is configured, update `Frontend/config_frontend.py` with the correct backend addresses:

```python
BACKEND_IPS = {
    "franka": "tcp://<franka-pc-ip>:5555",
    "ur":     "tcp://<ur-backend-ip>:5555",
    "mock":   "tcp://localhost:5555",
}
```

Use the **Ping Backend** button in the frontend GUI to verify the connection before issuing commands. A green indicator confirms the backend is reachable. If it stays red, check that the backend is running, the IPs are correct, and port `5555` is not blocked by the firewall.