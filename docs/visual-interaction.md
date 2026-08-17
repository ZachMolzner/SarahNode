# Phase 5C — Controlled Visual Interaction (Experimental Foundation)

Phase 5C begins the transition from read-only screen reasoning to constrained visual control. This first slice intentionally supports only pointer preview and one confirmed left click on a freshly revalidated visual target.

## Current supported behavior

Sarah can distinguish guidance from an explicit action:

```text
Which button should I click to continue?   # read-only reasoning
Click Not now                              # visual action
Move cursor to Search the web              # pointer preview only
```

For an explicit pointer move, Sarah:

1. Captures a fresh screenshot.
2. Uses the local vision model to locate the named control.
3. Requires a usable normalized bounding box and target match confidence.
4. Converts the normalized target center to the physical coordinates of the captured monitor.
5. Moves the pointer without clicking.

For an explicit click request, Sarah:

1. Performs the same fresh visual localization.
2. Moves the pointer to preview the target.
3. Stages a pending click for at most two minutes.
4. Does **not** click until the user confirms.
5. On confirmation, captures the screen again and re-locates the same semantic target.
6. Refuses the click if the target disappeared, changed identity, or cannot be located reliably.
7. Briefly hides SarahNode so its own window cannot intercept the target coordinate.
8. Performs one left click through the permission-checked internal pointer tool.
9. Restores SarahNode and performs a fresh visual verification pass.

Any intervening user request invalidates the pending visual click.

## Confirmation levels

Every click is a MEDIUM-risk action and requires confirmation through `screen.click`.

Ordinary visible controls use:

```text
confirm click
```

Controls whose requested/visible identity contains obviously consequential terms such as Delete, Install, Buy, Submit, Send, Allow, Grant, Reset, Format, or Uninstall require:

```text
confirm consequential click
```

The stronger classification is intentionally conservative and does not replace future application-specific risk understanding.

## Permission boundary

Phase 5C adds the narrow scopes:

- `screen.pointer`
- `screen.click`

`screen.pointer` is LOW risk and may execute only for an explicit deterministic pointer-move/visual-click preview request.

`screen.click` is MEDIUM risk and the click tool has `requires_confirmation=True`.

The raw `move_pointer` and `click_pointer` tools are registered so they still pass through ToolRegistry authorization, but they are marked `model_visible=False`. Neither the local conversation model nor a cloud model receives their raw coordinate schemas.

Broad `desktop.control` and `system.control` remain ungranted.

## Coordinate safety

- Users do not provide raw screen coordinates through this visual flow.
- Physical coordinates are derived from a fresh visual target bounding box.
- Coordinates are checked against the Windows virtual desktop bounds.
- SarahNode enables per-monitor DPI awareness before backend startup so screenshot and pointer coordinates stay aligned on scaled displays.
- Multi-monitor origins, including negative X/Y coordinates, are supported by the normalized-to-physical translation.

## Deliberately not implemented yet

This foundation does **not** provide:

- keyboard typing
- hotkeys
- Enter/Escape injection
- scrolling
- right-click
- double-click
- drag and drop
- arbitrary raw coordinate clicking from conversation
- continuous screen monitoring
- autonomous click chains
- unattended visual automation

Those should be added only after pointer/click accuracy is validated on the user's Windows machine.

## Status

The Phase 5C foundation is **experimental and not yet accepted by Windows manual testing**. The next manual validation should begin with pointer movement only, then a harmless click such as dismissing a non-consequential browser notification. Do not test Delete, Install, purchase, submission, account/security, or permission controls first.
