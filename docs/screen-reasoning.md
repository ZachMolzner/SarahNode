# Phase 5B — Visual Reasoning and Action Planning

Phase 5B extends SarahNode's explicit, read-only screen awareness with structured visual reasoning. Sarah can now describe visible content, read text, diagnose visible errors, locate UI controls, and recommend a next step without controlling the mouse or keyboard.

## Supported request types

Examples:

```text
What is on my screen?
Read the text on my screen.
Look at this error and tell me what to do.
Find the Save button.
Where is the search box?
Which button should I click to continue?
What should I click next?
```

Visual requests are routed deterministically to one of five modes:

- `describe`
- `read`
- `diagnose`
- `locate`
- `plan`

## Target localization

For locate/plan/diagnose requests, the local vision model is asked for structured output. When a UI target is visibly identifiable, Sarah records:

- label
- UI role
- visible text
- confidence
- normalized bounding box `[left, top, right, bottom]`

Bounding-box coordinates use a 0–1000 coordinate space over the captured monitor. The screen capture also records the monitor origin and dimensions in memory for that turn, which gives a future controlled-input layer enough information to translate a fresh visual target into physical screen coordinates.

Sarah does not invent a bounding box when the target is unclear.

## Safety boundary

Phase 5B remains read-only.

Sarah may explain what a visible control appears to do and recommend a next step, but she must not claim to have clicked, typed, submitted, purchased, installed, deleted, or changed anything.

If a recommended visual action could delete data, install software, grant permissions, send/submit content, make a purchase, change account/security settings, or expose secrets, Sarah is instructed to flag it as consequential.

Screen pixels remain ephemeral and are not written to disk or persistent memory.

## Manual verification

With another application visible behind SarahNode, try:

```text
Find the Save button.
Which button should I click to continue?
Look at this error and tell me what to do.
Where is the search box?
Read the main text on my screen.
```

Expected behavior:

- Sarah briefly captures the current monitor as in Phase 5A.
- She answers from the fresh screenshot.
- Locate/plan requests should include a useful location such as upper-right/lower-left when the target is clear.
- Plan/diagnose requests may include numbered suggested steps.
- Consequential visible actions should include a caution.
- Sarah must not move the mouse or interact with the interface in this phase.
