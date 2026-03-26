# Speech-to-Code Generation for Collaborative Robots

Software repository for the master's thesis *Speech-to-Code Generation for Collaborative Robots — A Modular Framework for Multi-Vendor Robot Programming in Structured Workspaces* at University West, Department of Engineering Science.

> **Status:** Work in progress. The framework is functional and usable for its intended purpose, but development is ongoing and the codebase will change until thesis submission.

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
└── Setup/           — Installer and uninstaller scripts, setup guide pyproject.toml   — Python dependency definitions (managed by uv)
```

---

## Installation

See the [Setup Guide](Setup/README.md) for full installation instructions.

The framework ships with one-command installers for Windows 11:

```powershell
# Frontend
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_frontend.ps1 | iex

# Backend
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/main/Setup/setup_backend.ps1 | iex
```

Both require PowerShell running as Administrator.

---

## Requirements

- **Frontend:** Windows 11, [LM Studio](https://lmstudio.ai) with `meta-llama-3.1-8b-instruct` loaded and served locally
- **Backend (UR / Mock):** Windows 11
- **Backend (Franka):** Ubuntu 20.04 with RT kernel, ROS Noetic, MoveIt — see setup guide

---

## Thesis

**Title:** Speech-to-Code Generation for Collaborative Robots  
**Author:** Sandy Meister  
**Programme:** Master in Robotics and Automation, University West  
