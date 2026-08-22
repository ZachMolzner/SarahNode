# Phase 5C — Controlled Visual Interaction

Phase 5C transitions Sarah from read-only screen reasoning to constrained desktop interaction. The Windows pointer/click loop is now manually validated. Phase 5C.2 adds experimental literal typing and bounded vertical scrolling while preserving the same deterministic permission boundary.

## Target localization

For standard Windows controls Sarah now prefers **Windows UI Automation (UIA)** instead of asking the vision model to invent coordinates. UIA supplies an accessible name, control type, visible/off-screen state, and physical bounding rectangle. SarahNode is hidden briefly during lookup so its own chat UI cannot satisfy the target query.

If UIA cannot find a useful named control, local vision grounding remains a fallback.

Users and language models never supply raw coordinates to the input tools.

## Pointer movement and confirmed click — validated

Examples:

```text
Move cursor to Seven
Click Seven
confirm click
```

For an explicit pointer move, Sarah locates the named control, validates the target match, converts its bounding rectangle to physical desktop coordinates, and moves the pointer without clicking.

For a click request Sarah:

1. Locates and previews the target.
2. Stages the click for at most two minutes.
3. Does **not** click until the user confirms.
4. Re-locates the same semantic target after confirmation.
5. Refuses to click if the target moved, disappeared, or changed identity.
6. Briefly hides SarahNode so it cannot intercept the click.
7. Performs exactly one left click.
8. Restores SarahNode and performs a fresh visual verification pass.

Ordinary clicks use:

```text
confirm click
```

Obviously consequential controls such as Delete, Install, Buy, Submit, Send, Allow, Grant, Reset, Format, or Uninstall require:

```text
confirm consequential click
```

The locate → move → confirm → re-locate → click → verify loop was manually validated on Windows with the Calculator `Seven` control on 2026-08-22.

## Phase 5C.2 literal typing — experimental

Example:

```text
Type "hello from Sarah" into Address and search bar
confirm type
```

Typing is intentionally narrower than general keyboard automation:

1. Sarah must locate a named text-entry control first.
2. The field is previewed without focusing or typing.
3. The user must reply `confirm type` within two minutes.
4. Sarah re-locates and re-validates the field.
5. Password/PIN/verification-code/token/secret fields are rejected.
6. Sarah performs one confirmed focus click.
7. Sarah sends only the exact literal Unicode text supplied by the user.
8. Sarah does **not** press Enter, Tab, Escape, or any shortcut afterward.
9. Clipboard paste is not used.
10. A fresh screen verification checks whether the field visibly changed without repeating the entered text.

A single typing action is limited to 500 characters. Control characters, newlines, Enter, and Tab are rejected by the low-level tool even if a higher layer makes a mistake.

## Phase 5C.2 bounded scrolling — experimental

Examples:

```text
Scroll down
Scroll up 2 steps
```

Scrolling is limited to vertical mouse-wheel input only. The default is three wheel steps and an explicit request is capped at five steps. Horizontal scrolling and unbounded repetition are not available.

Sarah briefly hides her own window, performs the bounded scroll, restores herself, and then visually checks whether the visible content moved.

## Permission boundary

Phase 5C uses four narrow scopes:

- `screen.pointer` — LOW risk
- `screen.click` — MEDIUM risk, confirmed
- `screen.type` — MEDIUM risk, confirmed
- `screen.scroll` — LOW risk, bounded

The internal tools are:

- `move_pointer`
- `click_pointer`
- `type_text`
- `scroll_pointer`

All four are registered with ToolRegistry but marked `model_visible=False`. Neither the local conversation model nor a cloud model receives their raw coordinate, text-input, or wheel schemas.

Broad `desktop.control` and `system.control` remain ungranted.

## Coordinate and input safety

- Physical coordinates come from a fresh UIA/vision target, never conversational coordinates.
- Coordinates are checked against Windows virtual desktop bounds.
- Per-monitor DPI awareness is enabled so screenshot/UIA and pointer coordinates remain aligned on scaled displays.
- Multi-monitor origins, including negative X/Y positions, are supported.
- Typing uses Windows `SendInput` Unicode events rather than shell commands or clipboard paste.
- Arbitrary key sequences are not implemented.
- Password-style UIA fields are marked and blocked from typing.

## Still deliberately unavailable

Phase 5C.2 does **not** provide:

- Enter/Escape/Tab injection
- Ctrl/Alt/Win shortcuts or arbitrary hotkeys
- right-click
- double-click
- drag and drop
- horizontal scrolling
- raw coordinate clicking from conversation
- continuous screen monitoring
- autonomous multi-step visual action chains
- unattended visual automation

## Status

- Phase 5C.1 pointer + confirmed single-click loop: **Windows user-verified**.
- Phase 5C.2 literal typing + bounded scrolling: **implemented, awaiting Windows manual acceptance testing**.
