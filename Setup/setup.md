# Setup Frontend 

> **Requires Administrator PowerShell.**  
> Right-click PowerShell → *Run as Administrator*, then paste the command below.

---

## Prerequisites

LM Studio must be installed and configured manually:
1. Download from [lmstudio.ai](https://lmstudio.ai)
2. Load `meta-llama-3.1-8b-instruct`
3. Start the local server before launching the app

---

## Install

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/setup_frontend.ps1 | iex
```

The script will:
- Install `ffmpeg` and `uv` via winget (if not present)
- Download and extract the frontend to `C:\Program Files\Speech-to-Cobot`
- Create a Desktop shortcut
- Pre-download the Whisper base model (~140 MB)

---

## Uninstall

```powershell
irm https://raw.githubusercontent.com/Meisdy/Speech-to-Code-Generation-for-Collaborative-Robots/dev/Setup/uninstall_frontend.ps1 | iex
```

The script will prompt before removing:
- Install directory (`C:\Program Files\Speech-to-Cobot`)
- Desktop shortcut
- Whisper model cache
- `ffmpeg` and `uv` (optional — you will be asked)

> LM Studio must be removed manually via **Settings → Apps**.