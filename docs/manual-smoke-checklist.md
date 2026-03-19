# SarahNode Desktop Polish Smoke Checklist

Use this after any desktop shell or presentation polish changes.

## Cold launch + persisted mode
- [ ] Launch with persisted `overlayMode=true`; verify startup mode is overlay immediately (no immersive flash).
- [ ] Launch with persisted `overlayMode=false`; verify startup mode is immersive immediately.

## Tray + visibility behavior
- [ ] Tray `Show Sarah` while hidden restores + focuses one window instance.
- [ ] Tray `Hide Sarah` while hidden is harmless (idempotent).
- [ ] Tray `Show Sarah` while visible keeps focus behavior stable (no flicker/minimize loop).
- [ ] Tray `Always on top` checkmark matches actual window always-on-top state.
- [ ] Tray `Overlay mode` checkmark matches the active display mode.
- [ ] Tray `Hide on close (tray)` checkmark matches in-app settings toggle.

## Close behavior + summon
- [ ] With `Hide on close (tray)=on`, window close button hides to tray.
- [ ] With `Hide on close (tray)=off`, window close button closes the app window normally.
- [ ] `Ctrl+Shift+Space` summon while hidden restores and focuses the window.
- [ ] `Ctrl+Shift+Space` summon while visible brings Sarah to front cleanly.

## Settings parity
- [ ] Toggling `Always on top` in settings updates tray checkmark immediately.
- [ ] Toggling `Overlay companion mode` in settings updates tray checkmark immediately.
- [ ] Toggling `Hide to tray on close` in settings updates tray checkmark immediately.
- [ ] Restart app and verify all three persisted desktop toggles restore correctly.

## Web-grounded panel behavior
- [ ] New grounded answer shows panel + presenting behavior.
- [ ] Identical grounded payload twice does not replay voice presentation.
- [ ] Newer grounded payload replaces older content.
- [ ] Panel auto-dismisses when untouched.
- [ ] Hovering/focusing panel pins it temporarily.
- [ ] Source expansion works with and without URLs.

## Quit path
- [ ] Tray `Quit SarahNode` exits fully and leaves no background UI process.
