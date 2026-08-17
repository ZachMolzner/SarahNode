# Phase 4D — Multi-action plans and reliable app shutdown

Phase 4D builds on the safe desktop action and confirmed mutation layers.

## Reliable app close

Normal `close`, `quit`, and `exit` requests remain confirmed actions. Sarah now separates an app's launcher name from the process names Windows actually uses. This is important for packaged apps such as Calculator, where `calc.exe` may launch a process such as `CalculatorApp.exe`.

After confirmation Sarah:

1. finds the app's visible windows,
2. sends the normal Windows close message,
3. waits briefly,
4. verifies that the visible windows actually disappeared.

Browser/helper processes may remain in the background without counting as an open visible app.

If a normal close is ignored, Sarah reports that the app stayed open and suggests an explicit force-close request instead of silently escalating.

## Force close / kill

Explicit phrases such as:

```text
Kill Opera
Force close VS Code
Terminate Calculator
```

route to a separate `terminate_app` tool.

This tool:

- uses the narrow `apps.terminate` permission scope,
- is HIGH risk,
- always requires explicit confirmation,
- can discard unsaved work,
- is limited to Sarah's supported app allowlist,
- blocks force termination of File Explorer because `explorer.exe` also hosts the Windows shell.

## Multi-action plans

Sarah can parse up to eight desktop/system actions from one request and execute them sequentially.

Examples:

```text
Open Opera, open Downloads, and bring VS Code to the front
Open Opera, Calculator, and Downloads
Close Calculator and Opera
Open Opera, then open example.com, then open Downloads
```

Shared verbs are supported for clear targets, so the user does not have to repeat `open` or `close` for every target.

Quoted text is protected from command splitting. For example, action words inside the content of a file being created are not interpreted as separate tasks.

## Confirmation semantics

If every step is low-risk, the plan can run immediately.

If any step requires confirmation, Sarah stages the entire plan and does not run any step yet. One `confirm` approves the whole staged plan. `cancel` discards the whole plan.

Pending plans:

- are isolated by user ID,
- expire after three minutes,
- exist only in memory,
- disappear when SarahNode restarts.

## Failure behavior

Plans execute in order and stop on the first failure. Later steps are not attempted after a failed or incomplete step.

This is intentional because sequential commands may depend on the state produced by earlier commands.

## Still out of scope

Phase 4D does not add:

- permanent file deletion,
- arbitrary process termination by PID or executable path,
- unrestricted shell/PowerShell execution,
- admin/elevation,
- registry changes,
- unrestricted `desktop.control` or `system.control`.
