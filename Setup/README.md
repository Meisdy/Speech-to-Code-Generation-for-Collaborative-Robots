# Setup Guide
## Speech-to-Code Generation for Collaborative Robots

This guide covers installation of the full system. The system has two components that run as separate processes — the **frontend** (operator machine) and the **backend** (machine connected to the robot). Both must be running for the system to function.

---

## System Overview

| Component                   | Machine             | OS                       |
|-----------------------------|---------------------|--------------------------|
| Frontend                    | Operator machine    | Windows 11               |
| Backend — Windows installer | Any Windows machine | Windows 11               |
| Backend — Franka Emika      | Dedicated Linux PC  | Ubuntu 20.04 (RT kernel) |

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
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_frontend.ps1 | iex
```

The script installs `ffmpeg` and `uv` via winget if not present, downloads the frontend to `C:\Program Files\Speech-to-Cobot`, creates a Desktop shortcut, and pre-downloads the Whisper small model (~466 MB).

### Launch

Double-click **Speech-to-Cobot** on the Desktop.

### Uninstall

Run the following in Administrator PowerShell, or run `uninstall_frontend.ps1` directly from the installation directory if internet is not available:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/uninstall_frontend.ps1 | iex
```

Removes the installation directory, Desktop shortcut, and Whisper model cache. Optionally removes `ffmpeg` and `uv` — you will be prompted for each. LM Studio must be removed manually via **Settings → Apps**.

---

## Part 2 — Backend: Windows Installer

This installer supports all robot adapters that run on Windows — currently **Mock** (no hardware required) and **Universal Robots**. The Franka adapter is not supported on Windows and requires the separate Linux setup described in Part 3.

### Install

Open PowerShell as Administrator and run:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_backend.ps1 | iex
```

The script installs `uv` via winget if not present, downloads the backend to `C:\Program Files\Speech-to-Cobot-Backend`, and creates a Desktop shortcut.

### Launch

Double-click **Speech-to-Cobot Backend** on the Desktop. A terminal window opens showing server logs. Keep this window open while the frontend is running. Press `Ctrl+C` to stop the server.

### Configuration

Before running with a real UR robot, verify the following in `Backend\config_backend.py`:

- `BINDING_ADDRESS` — ZeroMQ binding address (default: `tcp://*:5555`)
- `PC_IP` — IP address of the backend machine as seen by the UR robot (required for motion callback — not used for Franka)

The robot IP is configured in the UR controller at `Backend\robot_controllers\ur_controller.py` (`DEFAULT_ROBOT_IP`).

### Uninstall

Run the following in Administrator PowerShell, or run `uninstall_backend.ps1` directly from the installation directory if internet is not available:

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/uninstall_backend.ps1 | iex
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

Once the ROS stack is confirmed working, install the backend Python dependencies into the ROS Python environment.

### Launch

Start the backend server (from the right directory):

```bash
python -m Backend.main
```

The backend connects to the robot at `192.168.1.100` by default. Verify the robot IP in `Backend/robot_controllers/franka_controller.py` (`ROBOT_IP`).

---

## Part 4 — Robot Preparation (Per-Session)

These steps are required before each evaluation or usage session.
They cover physical robot preparation and are distinct from the software
installation steps in Parts 1–3.

---

### UR10e

1. Power on the UR10e via the Start Button on the Teach Pendant
2. After Startup, On the UR pendant, set the robot mode to **Remote Mode** (top right corner)
3. *(First-time only)* Verify the robot's IP address:
   `Menu → About → IP address`. Robot IPs are typically pre-configured
   to a consistent address (and can be modified) — confirm it matches `DEFAULT_ROBOT_IP` in
   `Backend/robot_controllers/ur_controller.py`.
4. Plug the robot Ethernet cable into the robot and the backend machine.
5. *(First-time only)* Configure the laptop Ethernet adapter with a static
   IP on the same subnet as the robot
6. Launch the frontend and the backend server on the machine. When all IPs are correct and the network connection is working, the frontend's **Ping Backend** button will show a green indicator and the system is ready.

   > **Note:** Always set Remote Mode before a session. If the robot is left in Local Mode, motion commands will silently fail — the backend sends the command, the robot acknowledges it, but does not move. Gripper and save-position commands continue to work normally in Local Mode, which can make the root cause hard to identify. Always confirm Remote Mode is active before proceeding.

---

### Franka Emika Panda

1. Power on the Franka controller using the controller switch
2. Start the Linux PC (running the real-time kernel)
3. Connect the robot controller to the Linux PC via Ethernet
4. *(First-time only)* Configure the Linux PC Ethernet adapter with a static IP
   on the same subnet as the robot
5. Connect the frontend machine to the Linux PC via Ethernet
6. *(First-time only)* Configure both Ethernet adapters (Linux PC and operator machine)
   with static IPs on the same subnet. Update `BACKEND_IPS` in `Frontend/config_frontend.py`
   with the resulting addresses
7. Open a browser and navigate to `https://<franka-robot-ip>`. Accept the certificate
   warning — Desk uses a self-signed certificate
8. Unlock the joints using the Desk interface
9. Engage the latching button (connected to X4 on the Arm base) once — the robot
   indicator changes from purple *(after startup only)* to white (hand-guide mode)
10. Release the latching button to exit hand-guide mode — the indicator turns blue (Ready)
11. In Desk, click **Activate FCI** — the indicator stays blue, FCI window appears
12. Start the backend on the Linux PC
13. Start the frontend on the operator machine. When all IPs are correct and the backend
    is reachable, the **Ping Backend** button shows a green indicator and the system is ready

> **Note:** The Franka must be in Ready (blue) state for motion commands to execute.
> If left in hand-guide mode (white), the robot accepts commands but will not execute them.

---

## Configuration Files

Both components have a single configuration file that covers all runtime parameters. Edit these files to configure the system for your environment.

**Frontend — `Frontend/config_frontend.py`**

| Parameter                  | Description                                                    |
|----------------------------|----------------------------------------------------------------|
| `ASR_MODEL_SIZE`           | Whisper model size: `tiny`, `base`, `small`, `medium`, `large` |
| `LLM_API_BASE`             | LM Studio server URL (default: `http://localhost:1234/v1`)     |
| `LLM_MODEL_NAME`           | Model name as shown in LM Studio                               |
| `BACKEND_IPS`              | ZeroMQ addresses for each robot backend                        |
| `ROBOT_TYPE_KEYS`          | Maps GUI display names to backend robot types                  |
| `MAX_ATTEMPTS`             | Retry attempts when backend is unreachable (default: 2)        |
| `ASR_LANGUAGE`             | ISO language code for ASR (default: `en`)                      |
| `ASR_SAMPLE_RATE`          | Audio sample rate in Hz — Whisper expects 16000                |
| `ASR_CONFIDENCE_THRESHOLD` | Warn on transcripts below this threshold (0.0–1.0)             |
| `LOGGING_LEVEL`            | Console log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`     |
| `LOGGING_LEVEL_FILE`       | File log verbosity (can be more verbose than console)          |
| `LOGGING_SAVE_AUDIO`       | Save microphone input as `.wav` for debugging                  |
| `LOGGING_SAVE_PARSE`       | Save parsed JSON for parser debugging                          |

**Backend — `Backend/config_backend.py`**

| Parameter            | Description                                                                              |
|----------------------|------------------------------------------------------------------------------------------|
| `BINDING_ADDRESS`    | ZeroMQ binding address (default: `tcp://*:5555`)                                         |
| `ZMQ_TIMEOUT_MS`     | ZeroMQ socket timeout in milliseconds (default: 1000)                                    |
| `AVAILABLE_ROBOTS`   | List of adapters to load: `mock`, `ur`, `franka`                                         |
| `PC_IP`              | IP of the backend machine as seen by the UR robot (required for UR motion callback only) |
| `LOGGING_LEVEL`      | Console log verbosity                                                                    |
| `LOGGING_LEVEL_FILE` | File log verbosity                                                                       |

The frontend connects to the backend via ZeroMQ on port `5555`. How you configure the network depends on your physical setup.

**Via router or switch:** assign static IPs to all devices on the same subnet, or use DHCP and update `config_frontend.py` with the correct backend IP. No adapter configuration is needed beyond a normal network connection.

**Direct Ethernet connection (no router):** the connecting adapter on the operator machine must be set to a static IP on the same subnet as the target device. On Windows 11: Settings → Network & Internet → Advanced network settings → select the adapter → Edit → Manual → IPv4, set IP and subnet mask (`255.255.255.0`), no gateway. Windows saves this per adapter, so it persists for that cable or dongle.

Once the network is configured, update `Frontend/config_frontend.py` with the correct backend addresses:

```python
BACKEND_IPS = {
    "franka": "tcp://192.168.2.20:5555",    # Linux PC running Franka backend
    "ur":     "tcp://localhost:5555",         # UR backend runs on operator machine
    "mock":   "tcp://localhost:5555",
}
```

Use the **Ping Backend** button in the frontend GUI to verify the connection before issuing commands. A green indicator confirms the backend is reachable. If it stays red, check that the backend is running, the IPs are correct, and port `5555` is not blocked by the firewall.
