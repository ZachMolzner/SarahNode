# Phase 5C — Controlled Visual Interaction

Phase 5C transitions Sarah from read-only screen reasoning to constrained desktop interaction. Phase 5C.1 pointer/click and Phase 5C.2 typing/scrolling have Windows acceptance coverage. Phase 5C.3 adds a narrow controlled-keyboard layer and is being hardened through Windows acceptance testing.

## Target localization

For standard Windows controls Sarah prefers **Windows UI Automation (UIA)** instead of asking the vision model to invent coordinates. UIA supplies an accessible name, control type, visible/off-screen state, and physical bounding rectangle. SarahNode is hidden briefly during lookup so its own chat UI cannot satisfy the target query.

UIA lookup receives a short retry before local vision grounding is used. Users and language models never supply raw screen coordinates to the input tools.

## Pointer movement and confirmed click — validated

```text
Move cursor to Seven
Click Seven
confirm click
```

A click is previewed first, staged for at most two minutes, freshly re-located after confirmation, and refused if the semantic target changed. Sarah hides herself before the physical click so her own window cannot intercept it. Ordinary clicks use `confirm click`; obviously consequential controls require `confirm consequential click`.

The locate → move → confirm → re-locate → click → verify loop was manually validated on Windows with Calculator on 2026-08-22.

## Phase 5C.2 exact text entry — validated and hardened

```text
Type "weather in Phoenix" into Address and search bar
confirm type
```

Typing is intentionally narrower than general keyboard automation:

1. Sarah locates and previews a named text-entry control.
2. The user must reply `confirm type` within two minutes.
3. Sarah freshly re-locates the field.
4. Password/PIN/verification-code/token/secret fields are rejected.
5. For Windows UIA fields, Sarah uses a model-hidden confirmed `replace_text_value` tool backed by UI Automation `ValuePattern`.
6. The current field contents are replaced with exactly the user-supplied literal text; existing URLs/text are not concatenated with the new value.
7. No Enter, Tab, shortcut, control character, or clipboard paste is used.
8. Vision-only text targets are refused when Sarah cannot safely determine replacement semantics.

The original literal typing flow was manually validated on Edge. A later acceptance test exposed that click+SendInput could splice text into an existing URL, so standard UIA fields now use exact replacement rather than ambiguous append behavior.

## Phase 5C.2 bounded scrolling — validated

```text
Scroll down 2 steps
Scroll up 2 steps
```

Scrolling is vertical mouse-wheel input only, capped at five steps per request. Sarah verifies scroll movement by comparing before/after viewport screenshots locally; scroll verification does not depend on the vision model.

Both down and up scrolling were manually validated on Windows on 2026-08-22.

## Phase 5C.3 controlled keyboard actions — acceptance testing

Supported commands are limited to:

```text
Press Escape
Press Tab
Press Backspace
Press Arrow Up
Press Arrow Down
Press Enter
confirm enter
```

The model-hidden keyboard tools expose no raw virtual-key codes, modifiers, repeat counts, function keys, or arbitrary key names.

### Underlying-window receiver safety

An initial Windows test showed that merely hiding SarahNode did not guarantee Windows transferred keyboard focus: Backspace/arrows/Escape/Tab and staged Enter were reported as targeting `SarahNode`. The receiver path was therefore hardened.

For every controlled key Sarah now:

1. Hides SarahNode.
2. Enumerates visible top-level Windows windows in current z-order.
3. Selects the topmost visible window underneath Sarah.
4. Explicitly restores/raises/activates that exact HWND.
5. Verifies Windows granted foreground focus before any key primitive is invoked.
6. Presses exactly one allowlisted key.
7. Restores SarahNode afterward.

If Windows will not grant focus to the intended underlying window, Sarah refuses the key press.

### Enter safety

Enter remains MEDIUM risk because it can submit, send, search, navigate, purchase, install, or confirm depending on focus.

`Press Enter` stages the exact underlying receiver and does not press anything. `confirm enter` hides Sarah again, re-identifies the top underlying window, refuses if its HWND changed, explicitly activates the staged receiver, verifies foreground focus, and only then invokes `press_enter` with `confirmed=True` exactly once.

Any unrelated intervening request invalidates a pending Enter confirmation.

## Permission boundary

Phase 5C uses narrow scopes:

- `screen.pointer` — LOW risk
- `screen.click` — MEDIUM risk, confirmed
- `screen.type` — MEDIUM risk, confirmed
- `screen.scroll` — LOW risk, bounded
- `screen.keys` — LOW-risk allowlisted keys plus separately confirmed Enter

Internal model-hidden input tools include:

- `move_pointer`
- `click_pointer`
- `type_text` (legacy/fallback primitive, not used for standard UIA replacement)
- `replace_text_value`
- `scroll_pointer`
- `press_safe_key`
- `press_enter`

Broad `desktop.control` and `system.control` remain ungranted.

## Still deliberately unavailable

Phase 5C.3 does **not** provide Ctrl/Alt/Win shortcuts, arbitrary hotkeys, arbitrary letter/number key injection outside confirmed literal text entry, function keys, key holds/repeats, right-click, double-click, drag/drop, horizontal scrolling, raw coordinate clicking, continuous screen monitoring, or unattended visual automation.

## Status

- Phase 5C.1 pointer + confirmed single-click loop: **Windows user-verified**.
- Phase 5C.2 exact text entry + bounded scrolling: **Windows user-verified core, text replacement hardening awaiting retest**.
- Phase 5C.3 controlled keyboard actions: **receiver bug identified and hardened; awaiting Windows retest**.
