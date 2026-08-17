# Phase 4B — Safe desktop actions

Phase 4B adds a deliberately narrow action layer on top of SarahNode's read-only desktop awareness.

## Enabled low-risk actions

Sarah can:

- open or focus an allowlisted desktop application,
- bring an already-running allowlisted application to the foreground,
- open known folders such as Downloads, Documents, Desktop, Pictures, and the SarahNode repository,
- open an existing non-executable file by exact path,
- resolve and open one uniquely named non-executable file within the user's home folder,
- open `http://` and `https://` URLs in the default browser.

Supported application aliases currently include:

- Chrome
- Opera
- Microsoft Edge
- Visual Studio Code
- Steam
- Calculator
- Notepad
- File Explorer
- Windows Terminal

When `open_app` finds a visible existing instance, it attempts to focus that window instead of launching a duplicate.

## Safety boundary

Phase 4B does **not** grant broad `desktop.control`, `files.write`, or `system.control` permission.

The narrow scopes granted by default are:

- `apps.launch`
- `apps.focus`
- `files.open`
- `web.launch`

The following remain outside this phase:

- deleting, moving, renaming, or overwriting files,
- terminating processes,
- installing or uninstalling software,
- executing arbitrary shell commands,
- running arbitrary executable paths,
- changing system settings,
- registry changes,
- elevated/admin actions.

The safe file opener blocks executable/script/shortcut/installer/registry file types and common macro-enabled Office formats. The safe URL opener accepts only HTTP and HTTPS URLs.

## Deterministic routing

Clear commands are routed before LLM inference so local-model tool-call reliability is not required for basic actions.

Examples:

```text
Open Opera
Open my Downloads folder
Open budget.xlsx
Open https://github.com
Bring VS Code to the front
Switch to Steam
```

Ambiguous or destructive phrases are intentionally not auto-routed.

Examples that should not execute automatically:

```text
Delete my Downloads folder
Kill Chrome
Install Discord
Open the thing we discussed
```

## Verification sequence

After pulling the latest `main`, restart SarahNode and test:

```text
Open Calculator
Open Opera
Bring VS Code to the front
Open my Downloads folder
Open SarahNode folder
Open example.com
```

For file opening, create or use a harmless uniquely named `.txt`, `.pdf`, `.docx`, or `.xlsx` file and ask Sarah to open it by name. If multiple files have the same name, Sarah should ask for an exact path rather than guessing.

Then verify blocked actions remain blocked/not auto-routed:

```text
Open setup.exe
Open script.ps1
Delete a file
Kill Opera
```

## Next control layer

A later phase can add stronger actions such as file mutations and process control, but they should use explicit confirmation and stronger permission scopes rather than extending the low-risk Phase 4B scopes.
