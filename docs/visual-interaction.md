# Phase 5C — Controlled Visual Interaction

Phase 5C transitions Sarah from read-only screen reasoning to constrained desktop interaction. The Windows pointer/click loop and Phase 5C.2 literal typing/bounded scrolling are now manually validated. Phase 5C.3 adds a deliberately narrow controlled-keyboard layer without exposing arbitrary key injection.

## Target localization

For standard Windows controls Sarah prefers **Windows UI Automation (UIA)** instead of asking the vision model to invent coordinates. UIA supplies an accessible name, control type, visible/off-screen state, and physical bounding rectangle. SarahNode is hidden briefly during lookup so its own chat UI cannot satisfy the target query.

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
8. Restores SarahNode and performs a fresh verification pass.

Ordinary clicks use:

```text
confirm click
```

Obviously consequential controls such as Delete, Install, Buy, Submit, Send, Allow, Grant, Reset, Format, or Uninstall require:

```text
confirm consequential click
```

The locate → move → confirm → re-locate → click → verify loop was manually validated on Windows with the Calculator `Seven` control on 2026-08-22.

## Phase 5C.2 literal typing — validated

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
10. A fresh verification checks whether the field visibly changed.

A single typing action is limited to 500 characters. Control characters, newlines, Enter, and Tab are rejected by the low-level typing tool even if a higher layer makes a mistake.

The Edge address-bar literal typing flow was manually validated on Windows on 2026-08-22.

## Phase 5C.2 bounded scrolling — validated

Examples:

```text
Scroll down
Scroll up 2 steps
```

Scrolling is limited to vertical mouse-wheel input only. The default is three wheel steps and an explicit request is capped at five steps. Horizontal scrolling and unbounded repetition are not available.

Sarah briefly hides her own window, captures the viewport, performs the bounded scroll, captures again, restores herself, and compares the before/after frames locally. Scroll verification does not depend on the vision model.

Both downward and upward two-step scrolling were manually validated on Windows on 2026-08-22.

## Phase 5C.3 controlled keyboard actions — experimental

Supported commands are intentionally limited to:

```text
Press Escape
Press Tab
Press Backspace
Press Arrow Up
Press Arrow Down
Press Enter
confirm enter
```

The low-level keyboard layer exposes only two internal tools:

- `press_safe_key` — exactly one Escape, Tab, Backspace, Arrow Up, or Arrow Down press.
- `press_enter` — exactly one Enter press and always requires confirmation.

There is no raw virtual-key parameter, modifier parameter, repeat count, function-key access, or arbitrary key name.

### Enter safety

Enter is always treated as MEDIUM risk in Phase 5C.3 because its effect depends on focus and it can submit, send, search, navigate, purchase, install, or confirm an action.

When the user asks `Press Enter`, Sarah:

1. Briefly hides herself and identifies the underlying foreground Windows window.
2. Stages that exact receiving window for at most two minutes.
3. Does **not** press Enter yet.
4. Requires the explicit phrase `confirm enter`.
5. Hides herself again and re-checks the receiving window.
6. Refuses Enter if the foreground window handle changed.
7. Invokes the model-hidden `press_enter` tool with `confirmed=True`.
8. Presses Enter exactly once with no modifiers.
9. Performs a local before/after viewport comparison when available.

Any unrelated intervening request invalidates the pending Enter confirmation.

### Escape, Tab, Backspace, and arrows

These five keys are LOW risk but still deliberately bounded: one explicit request produces exactly one key press. Sarah hides her own window first so the underlying application receives the input. No automatic repetition is available.

## Permission boundary

Phase 5C uses five narrow scopes:

- `screen.pointer` — LOW risk
- `screen.click` — MEDIUM risk, confirmed
- `screen.type` — MEDIUM risk, confirmed
- `screen.scroll` — LOW risk, bounded
- `screen.keys` — LOW-risk allowlisted keys plus separately confirmed Enter

The internal input tools are:

- `move_pointer`
- `click_pointer`
- `type_text`
- `scroll_pointer`
- `press_safe_key`
- `press_enter`

All are registered with ToolRegistry but marked `model_visible=False`. Neither the local conversation model nor a cloud model receives raw coordinate, literal-input, wheel, or controlled-key schemas.

Broad `desktop.control` and `system.control` remain ungranted.

## Coordinate and input safety

- Physical coordinates come from a fresh UIA/vision target, never conversational coordinates.
- Coordinates are checked against Windows virtual desktop bounds.
- Per-monitor DPI awareness is enabled so screenshot/UIA and pointer coordinates remain aligned on scaled displays.
- Multi-monitor origins, including negative X/Y positions, are supported.
- Literal typing uses Windows `SendInput` Unicode events rather than shell commands or clipboard paste.
- Controlled special keys use fixed Win32 virtual-key constants inside model-hidden code.
- Arrow keys use the Windows extended-key flag.
- Arbitrary key sequences, raw virtual-key values, repeat counts, and modifiers are not exposed.
- Password-style UIA fields remain blocked from literal typing.

## Still deliberately unavailable

Phase 5C.3 does **not** provide:

- Ctrl/Alt/Win shortcuts or arbitrary hotkeys
- arbitrary letter/number key injection outside the confirmed literal typing flow
- function keys
- key holds or repeated key presses
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
- Phase 5C.2 literal typing + bounded scrolling: **Windows user-verified**.
- Phase 5C.3 controlled keyboard actions: **implemented with regression tests; awaiting Windows manual acceptance testing**.
