# SarahNode

SarahNode is a local-first personal technical assistant focused on **IT troubleshooting, coding, research, and general questions**.

Sarah is represented in the desktop app by a display-only 3D avatar, but she does **not** inspect or operate the user's screen. Screen capture, pointer control, keyboard injection, UI Automation control, app launching, file mutation, and browser-driving workflows are not part of the active runtime.

## Core goals

- Help diagnose Windows, networking, hardware, software, printer, Active Directory, ServiceNow, and other IT problems using an evidence-first troubleshooting flow.
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
- live web-grounded research through a no-key Bing RSS provider by default, with Brave/SerpAPI available as optional providers
- persistent non-secret memory
- safe outcome learning from user-confirmed fixes and explicit corrections
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

Sarah's display behavior also includes:
- emotion inference from both reply wording and emoji;
- distinct happy, relaxed, sad, angry, surprised, and concerned facial recipes;
- idle standing, short pacing, and seated-rest behavior;
- automatic standing/centering and forward attention when the user begins typing, sends a message, or Sarah starts thinking/speaking;
- Full/Face camera modes and interactive zoom.

## Avatar expression test

The chat includes a local slash command for testing MANUKA's facial expressions without sending anything to Qwen:

```text
/face-test
/face-test happy
/face-test relaxed
/face-test sad
/face-test angry
/face-test surprised
/face-test concerned
/face-test neutral
```

`/face-test` and `/face-test all` automatically switch the avatar to Face view and cycle the expressions. A normal message exits test mode and returns emotion control to Sarah.

## Local voice

The desktop chat can speak Sarah's replies with the Windows/WebView speech-synthesis service. No ElevenLabs key is required for this frontend-local voice path.

- Voice is enabled by default and can be toggled with **Voice On / Voice Off** in the chat header.
- Sarah prefers English voices reported by the platform as local services.
- The avatar receives a real `speaking` state for the duration of local playback so mouth animation remains active while audio is playing.
- Markdown and code blocks are cleaned before speech so Sarah does not read formatting characters or long code listings aloud.
- The selected Voice On/Off preference persists between launches.

To request a particular installed voice by name, set:

```text
VITE_SARAH_VOICE_NAME=Zira
```

If that voice is unavailable, Sarah falls back to another local English voice and then to the platform default.

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

SarahNode defaults to a local Ollama/OpenAI-compatible model endpoint with latency-oriented settings:

```text
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=qwen3:14b
LOCAL_LLM_TEMPERATURE=0.35
LOCAL_LLM_MAX_TOKENS=700
LOCAL_LLM_REASONING_EFFORT=none
LOCAL_LLM_MAX_TOOL_ROUNDS=4
LLM_PROVIDER=local
```

For Ollama, Sarah requests no-thinking mode for everyday responses, sends only tool schemas relevant to the current turn, and uses a shorter response budget. These settings can be overridden in `backend/.env`.

## Live web research

SarahNode now defaults to a no-key public web-search provider:

```text
WEB_SEARCH_PROVIDER=bing_rss
```

Current/vendor-specific IT questions can therefore be web-grounded without an API key. Brave Search and SerpAPI remain available when their credentials are configured. Web pages are fetched concurrently to reduce research latency.

## Outcome learning

Sarah does not continuously retrain Qwen's model weights. Instead, she has a safe persistent learning loop for useful outcomes:

- when the user explicitly confirms a troubleshooting answer worked, Sarah stores the prior problem and successful answer as an `experience` memory;
- when the user says the actual fix was something else, Sarah stores that correction instead;
- similar future problems can retrieve those user-confirmed experiences;
- learned experiences are treated as prior evidence, not universal truth;
- generic thanks/acknowledgements do not become memories;
- credential/secret-shaped content is rejected by the same persistent-memory secret guard.

This makes Sarah improve from real outcomes without allowing her to reinforce her own unverified answers.

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
