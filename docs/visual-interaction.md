# Phase 5C — Controlled Visual Interaction

Phase 5C transitions Sarah from read-only screen reasoning to constrained desktop interaction. Phase 5C.1 pointer/click, Phase 5C.2 exact text entry/scrolling, and Phase 5C.3 controlled keyboard actions now have Windows acceptance coverage. Phase 5C.4 begins narrowly scoped multi-step computer-use workflows.

## Target localization

For standard Windows controls Sarah prefers **Windows UI Automation (UIA)** instead of asking the vision model to invent coordinates. UIA supplies an accessible name, control type, visible/off-screen state, and physical bounding rectangle. SarahNode is hidden briefly during lookup so its own chat UI cannot satisfy the target query.

UIA lookup receives a short retry before local vision grounding is used. Users and language models never supply raw screen coordinates to the input tools.

## Phase 5C.1 pointer movement and confirmed click — validated

```text
Move cursor to Seven
Click Seven
confirm click
```

A click is previewed first, staged for at most two minutes, freshly re-located after confirmation, and refused if the semantic target changed. Sarah hides herself before the physical click so her own window cannot intercept it. Ordinary clicks use `confirm click`; obviously consequential controls require `confirm consequential click`.

The locate → move → confirm → re-locate → click loop was manually validated on Windows with Calculator on 2026-08-22.

## Phase 5C.2 exact text entry — validated

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

The hardened Edge address-bar flow was manually validated on Windows on 2026-08-22.

## Phase 5C.2 bounded scrolling — validated

```text
Scroll down 2 steps
Scroll up 2 steps
```

Scrolling is vertical mouse-wheel input only, capped at five steps per request. Sarah verifies scroll movement by comparing before/after viewport screenshots locally; scroll verification does not depend on the vision model.

Both down and up scrolling were manually validated on Windows on 2026-08-22.

## Phase 5C.3 controlled keyboard actions — validated

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

### Verified receiver continuation

Windows acceptance testing exposed several unreliable receiver heuristics: hiding Sarah alone could leave SarahNode as foreground; generic z-order could choose Picture in Picture; and the current pointer position could resolve to the desktop shell (`Program Manager`) after the user moved the mouse back to Sarah's chat box.

The accepted design now uses a short-lived **verified receiver handoff**:

1. A successful grounded visual/text action resolves the top-level Windows HWND that owns the verified control coordinates while Sarah is hidden.
2. That app receiver is retained ephemerally for a few minutes, never persisted to long-term memory.
3. The next controlled key prefers that verified HWND rather than guessing from the user's new mouse position.
4. Sarah explicitly activates the HWND and verifies Windows granted foreground focus before sending the key.
5. `Program Manager`/desktop shell is never accepted as a keyboard receiver.
6. Successful controlled keys refresh the same short continuation window.

This was manually validated with Edge: exact address-bar replacement retained the Edge receiver, Backspace returned to Edge and changed the field, `Press Enter` staged the same Edge receiver without submitting, and `confirm enter` freshly re-verified Edge and pressed Enter once.

### Enter safety

Enter remains MEDIUM risk because it can submit, send, search, navigate, purchase, install, or confirm depending on focus.

`Press Enter` stages the exact verified receiver and does not press anything. `confirm enter` re-verifies the same HWND, explicitly activates it, and only then invokes the model-hidden `press_enter` tool with `confirmed=True` exactly once. Any unrelated intervening request invalidates the pending confirmation.

## Phase 5C.4 confirmed multi-step computer workflow — experimental

The first workflow is deliberately narrow:

```text
Open Edge and search for Dexcom desktop support
confirm search
```

Sarah interprets this as one fixed plan:

1. Open or focus Microsoft Edge (LOW risk; may run immediately).
2. Verify the Edge `Address and search bar` through Windows UI Automation.
3. Stage the exact user-supplied search query for at most two minutes.
4. Do **not** type or submit until the user replies `confirm search`.
5. Freshly re-locate the address bar after confirmation.
6. Resolve the top-level app HWND owning those verified coordinates.
7. Replace the address-bar contents with exactly the search query using the confirmed model-hidden UIA text tool.
8. Activate/verify the Edge receiver.
9. Invoke confirmed Enter exactly once.
10. Compare the before/after viewport locally and stop on the resulting page.

A search query that itself appears to contain a password, API key, access token, private key, authentication header, or similar credential is refused before Edge is opened.

Phase 5C.4 does **not** click a search result, choose links, fill forms, download files, continue browsing, or run an open-ended model-directed action loop.

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

The Phase 5C.4 coordinator composes these existing permissioned primitives; it does not add a raw automation/shell tool. Broad `desktop.control` and `system.control` remain ungranted.

## Still deliberately unavailable

Phase 5C.4 does **not** provide Ctrl/Alt/Win shortcuts, arbitrary hotkeys, arbitrary letter/number key injection outside confirmed literal text entry, function keys, key holds/repeats, right-click, double-click, drag/drop, horizontal scrolling, raw coordinate clicking, continuous screen monitoring, unattended visual automation, autonomous result clicking, or unrestricted multi-step browsing.

## Status

- Phase 5C.1 pointer + confirmed single-click loop: **Windows user-verified**.
- Phase 5C.2 exact text entry + bounded scrolling: **Windows user-verified**.
- Phase 5C.3 controlled keyboard actions + verified receiver handoff: **Windows user-verified**.
- Phase 5C.4 confirmed Edge search workflow: **implemented with regression tests; awaiting Windows acceptance testing**.
