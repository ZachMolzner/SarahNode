# Phase 5 — Screen Awareness

SarahNode Phase 5 adds explicit, read-only visual perception of the user's current Windows screen.

## Behavior

- Screen capture happens only when the user explicitly asks Sarah to inspect what is visible, for example:
  - `What is on my screen?`
  - `Look at my screen and tell me what error you see.`
  - `Read the text on my screen.`
  - `What am I looking at?`
- Normal chat, memory, automation, and desktop actions do not trigger screenshots.
- Screenshot pixels are encoded in memory and sent directly to the configured local vision model.
- Screenshots are not written to SarahNode's data directory and are not inserted into persistent memory.
- On Windows, Sarah captures the monitor containing the mouse cursor.
- If the SarahNode window itself is foreground, Sarah briefly hides her own window, captures the window/display underneath it, and restores SarahNode immediately afterward.
- The captured image is resized when necessary before vision inference to reduce latency and VRAM/RAM use.

## Local vision model

The default model is:

```powershell
ollama pull qwen3-vl:4b
```

The normal text/tool model remains `llama3.2` unless separately configured. The vision model is only requested for screen-inspection turns.

Configuration:

```text
SCREEN_AWARENESS_ENABLED=1
LOCAL_VISION_MODEL=qwen3-vl:4b
SCREEN_VISION_TIMEOUT_SECONDS=60
SCREEN_CAPTURE_MAX_DIMENSION=2560
SCREEN_CAPTURE_JPEG_QUALITY=88
SCREEN_HIDE_SARAH_DURING_CAPTURE=1
```

## Permissions and safety

Phase 5 adds the granular read-only permission `screen.read`.

This phase does **not** add visual clicking, typing, dragging, arbitrary UI automation, continuous screen recording, background monitoring, or screenshot history. Visual actions should be added later through the existing permission and confirmation system rather than coupling perception directly to unrestricted input control.

## Suggested manual verification

After installing backend requirements and pulling the vision model, start SarahNode and test:

```text
What is on my screen?
Look at my screen and tell me what application is open.
Read the main text on my screen.
What error do you see on my screen?
```

For the most useful test, put another application behind SarahNode, then ask Sarah to inspect the screen. SarahNode should briefly hide, capture what was underneath, restore itself, and answer from the fresh screenshot.
