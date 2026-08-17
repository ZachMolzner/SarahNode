# Phase 4C — Confirmed desktop changes

Phase 4C adds stronger local actions while keeping SarahNode's permission model narrow and explicit.

## Confirmation model

A supported mutation request is **staged first**. Nothing changes on the first request.

Example:

```text
You: Create folder SarahTest in Downloads
Sarah: This will create the folder "...\Downloads\SarahTest". Nothing has changed yet. Reply "confirm" within 3 minutes to proceed, or "cancel".
You: confirm
Sarah: Confirmed. Created the folder ...\Downloads\SarahTest.
```

Pending actions:

- are keyed by `user_id`,
- expire after 3 minutes,
- are stored only in memory,
- disappear when SarahNode restarts,
- execute through `ToolRegistry.invoke(..., confirmed=True)` only after confirmation.

The tool registry independently rejects these tools when `confirmed=False`, even if a local model attempts to call them directly.

## Enabled confirmed actions

### Create folders

```text
Create folder SarahTest in Downloads
```

### Create new text files

```text
Create file phase4c-test.txt in Downloads
Create file phase4c-note.txt in Downloads with text "Sarah Phase 4C test"
```

Files are created only if they do not already exist. Active/executable file types are blocked.

### Move or rename files/folders

```text
Rename phase4c-test.txt to phase4c-renamed.txt
Move phase4c-renamed.txt to Documents
```

Sarah will not overwrite an existing destination.

### Recycle files/folders

```text
Delete phase4c-renamed.txt
Move phase4c-renamed.txt to Recycle Bin
```

`delete` in Phase 4C means **move to the operating-system Recycle Bin**. Permanent deletion is not available.

### Close supported apps

```text
Close Calculator
Close Opera
Quit VS Code
```

Sarah sends a normal Windows close request (`WM_CLOSE`) to visible application windows. Phase 4C does not force-kill processes.

## Permission scopes

Phase 4C adds these narrow scopes:

- `files.create`
- `files.move`
- `files.recycle`
- `apps.close`

Each associated tool is `MEDIUM` risk and requires explicit confirmation.

Broad scopes remain ungranted:

- `files.write`
- `desktop.control`
- `system.control`

## File safety boundaries

Phase 4C file mutations are restricted to the current user's profile.

Sarah protects these subtrees completely:

- SarahNode repository
- AppData
- `.ssh`

Sarah also protects the top-level profile folders themselves from rename/recycle operations:

- Desktop
- Downloads
- Documents
- Pictures
- Music
- Videos

Items **inside** those standard folders can still be created, moved, renamed, and recycled.

## Not available in Phase 4C

The following remain intentionally unavailable:

- permanent deletion,
- forced process termination,
- arbitrary shell or PowerShell commands,
- arbitrary executable launching,
- installs/uninstalls,
- registry changes,
- administrator/elevated operations,
- system-setting changes,
- overwriting existing files.

## Verification sequence

After pulling `main`, install backend dependencies once because Phase 4C adds `send2trash`:

```powershell
cd C:\Users\karvo\SarahNode\backend
python -m pip install -r requirements.txt
```

Then restart SarahNode and test in this order:

```text
Create folder SarahPhase4CTest in Downloads
```

Verify Sarah asks for confirmation and the folder does **not** exist yet. Then:

```text
confirm
```

Next:

```text
Create file sarah-phase4c.txt in Downloads with text "Phase 4C works"
confirm
Rename sarah-phase4c.txt to sarah-phase4c-renamed.txt
confirm
Move sarah-phase4c-renamed.txt to Documents
confirm
Delete sarah-phase4c-renamed.txt
confirm
```

Verify the deleted file is in the Recycle Bin rather than permanently removed.

For app closing:

```text
Open Calculator
Close Calculator
```

Sarah should ask for confirmation before closing it.

Also verify cancellation:

```text
Create folder ShouldNotExist in Downloads
cancel
```

The folder must never be created.

Finally test protected boundaries:

```text
Delete Downloads
Rename SarahNode to SarahNodeOld
Kill Opera
```

Sarah should refuse/protect these rather than execute them.
