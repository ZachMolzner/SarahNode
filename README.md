# SarahNode

SarahNode is a local-first personal technical assistant focused on **IT troubleshooting, coding, research, and general questions**.

Sarah is represented in the desktop app by a display-only 3D avatar, but she does **not** inspect or operate the user's screen. Screen capture, pointer control, keyboard injection, UI Automation control, app launching, file mutation, and browser-driving workflows are not part of the active runtime.

## Core goals

- Help diagnose Windows, networking, hardware, software, printer, Active Directory, ServiceNow, and other IT problems.
- Explain, write, review, and debug code.
- Answer general questions and use web research when current information is needed.
- Remember useful non-secret preferences and project context.
- Offer read-only local diagnostics such as system resources and running-process information.
- Present Sarah as a local 3D character without giving the avatar desktop-control privileges.

## Architecture

```text
┌───────────────────────────────────────────────┐
│                 SarahNode UI                  │
│ React + TypeScript + Three.js + VRM           │
│                                               │
│  Display-only Sarah avatar  │  Chat interface │
└───────────────────────┬───────────────────────┘
                        │ REST / WebSocket
                        ▼
┌───────────────────────────────────────────────┐
│                 FastAPI backend               │
│ StreamOrchestrator + DialogueEngine           │
│ Safe persistent memory + secret guard         │
│ Model gateway + web research                  │
│ Read-only IT diagnostics                      │
└───────────────────────────────────────────────┘
```

The Tauri shell provides the Windows desktop application.

## What Sarah can do

Sarah's active runtime supports:

- IT and technical troubleshooting
- coding and debugging help
- general Q&A
- web-grounded research when configured
- persistent non-secret memory
- read-only system information
- CPU, memory, disk, and boot-time diagnostics
- read-only running-process inspection
- optional voice services
- display-only avatar state/presence

## What Sarah cannot do

SarahNode intentionally does not expose:

- screen capture or screen vision
- mouse movement or clicking
- keyboard injection
- UI Automation control
- autonomous browser control
- app launching/focusing/closing
- local file creation, movement, deletion, or opening through assistant tools
- unrestricted shell or system control

This boundary keeps Sarah focused on **helping the user solve problems** rather than operating the computer for them.

## MANUKA avatar

SarahNode can load a local VRM avatar from:

```text
frontend/public/models/sarah.vrm
```

The model file is intentionally ignored by Git. Licensed avatar assets should remain local and should not be redistributed through this public repository.

To install a local MANUKA VRM:

```powershell
cd C:\Users\karvo\SarahNode
.\scripts\install-manuka-avatar.ps1 "C:\path\to\MANUKA.vrm"
```

The frontend uses Three.js and `@pixiv/three-vrm` to render the character. Avatar motion is presentation-only and has no screen-reading or computer-control access.

### Appearance profiles

Sarah's avatar selector supports:

- `Default` — full original MANUKA costume.
- `Casual Streetwear` — separate local VRM inspired by the supplied streetwear reference.
- `Cafe Maid` — separate local maid outfit VRM.
- `Sporty Athleisure` — separate local sporty outfit VRM.
- `Elegant Evening` — separate local evening outfit VRM.
- `Cozy Sweater` — separate local oversized sweater outfit VRM.
- `Futuristic Idol / Techwear` — separate local idol/techwear outfit VRM.
- `Sexy` — a more minimal but still clothed version of the default VRM.
- `Underwear` — loads a separate local VRM at `frontend/public/models/sarah-underwear.vrm`.

The six reference outfits use these local file names:

```text
frontend/public/models/sarah-casual-streetwear.vrm
frontend/public/models/sarah-cafe-maid.vrm
frontend/public/models/sarah-sporty-athleisure.vrm
frontend/public/models/sarah-elegant-evening.vrm
frontend/public/models/sarah-cozy-sweater.vrm
frontend/public/models/sarah-futuristic-idol-techwear.vrm
```

### First-pass Blender outfit generator

SarahNode includes a Blender Python generator that uses MANUKA's humanoid bones to size and parent editable first-pass garment meshes. It creates the major silhouettes from the supplied references rather than pretending the source VRM already contains those outfits.

Run all six from PowerShell:

```powershell
cd C:\Users\karvo\SarahNode
.\scripts\build-manuka-outfits.ps1 -SourceBlend "C:\Users\karvo\MANUKA_ver1.02\MANUKA.blend"
```

During visual tuning, rebuild only one outfit so iteration is faster:

```powershell
.\scripts\build-manuka-outfits.ps1 `
  -SourceBlend "C:\Users\karvo\MANUKA_ver1.02\MANUKA.blend" `
  -Preset "casual-streetwear"
```

The generated editable Blender files are placed under:

```text
local/manuka-outfits/
```

If the VRM Add-on for Blender is installed and enabled, the builder also attempts to export each outfit directly into `frontend/public/models/`. Otherwise, open the generated `.blend` files, visually fit/tune the garments, and export each one to the expected VRM filename.

For a manually exported outfit VRM:

```powershell
.\scripts\install-manuka-outfit.ps1 "cafe-maid" "C:\path\to\MANUKA_cafe_maid.vrm"
```

The default MANUKA VRM does not expose the bra/panty as separate meshes, so SarahNode intentionally does not create Underwear mode by merely hiding the normal shirt/shorts. Export an underwear-specific VRM from the MANUKA Blender source, then install it locally:

```powershell
.\scripts\install-manuka-underwear-avatar.ps1 "C:\path\to\MANUKA_underwear.vrm"
```

All local avatar VRMs and generated outfit source files are Git-ignored and remain local to the installation.

## Local development

### Backend

```powershell
cd C:\Users\karvo\SarahNode\backend
python -m pip install -r requirements.txt
python run_server.py
```

### Frontend

```powershell
cd C:\Users\karvo\SarahNode\frontend
npm install
npm run dev
```

### Tauri desktop app

```powershell
cd C:\Users\karvo\SarahNode\frontend
$env:Path += ";$env:USERPROFILE\.cargo\bin"
$env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
npm run tauri:dev
```

## Model configuration

SarahNode defaults to a local OpenAI-compatible model endpoint:

```text
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=qwen3:14b
LLM_PROVIDER=local
```

Optional web-search providers can be configured through the backend environment file.

## Safety and memory

Persistent memory rejects credential-shaped values such as passwords, API keys, access tokens, recovery codes, and private keys. Secret-shaped chat content is also redacted from Sarah's rolling session-memory copy so later turns cannot retrieve it from recent conversation context.

## Project direction

The current priority order is:

1. stronger IT troubleshooting and diagnostic reasoning
2. better coding/repository workflows
3. higher-quality general and web-grounded answers
4. reliable safe memory
5. Sarah's display-only MANUKA avatar
6. optional voice interaction

Desktop-control and screen-interaction features are deliberately outside the project direction.
