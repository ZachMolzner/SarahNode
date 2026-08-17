# SarahNode JARVIS Roadmap

SarahNode's north-star is a permissioned personal AI operating layer: conversational, persistent, tool-using, proactive, and extensible across desktop, web, personal services, voice, devices, and smart-home systems.

## Core principles

1. Assistant-first: intelligence and capability before presentation.
2. One Sarah identity across interfaces.
3. Memory is structured and persistent, not just chat history.
4. Tools are modular and registered through a common contract.
5. Side effects are permission-gated and confirmation-aware.
6. No unrestricted shell/admin control by default.
7. Event-driven architecture for automation and proactive assistance.
8. Capabilities must be testable independently.

## Build phases

### Phase 1 — Sarah Core
- Model gateway contract
- Tool registry
- Permission scopes and risk levels
- Event bus
- Automation registry
- Capabilities endpoint
- Integrate existing memory/orchestration services

### Phase 2 — Real AI agent loop
- Replace mock responses with configured model provider
- Tool-call planning/execution loop
- Prompt/context assembly
- Error recovery and tool-result feedback
- Conversation persistence

### Phase 3 — Memory
- Profile memory
- Project memory
- Entity/relationship memory
- Event memory
- Recall and relevance ranking
- User-visible memory controls

### Phase 4 — Desktop and files
- Safe file search/read/write tools
- Application launching
- System information
- Screenshot capture
- Active-window context
- Notification service
- Permission prompts for write/control actions

### Phase 5 — Web intelligence
- Search and browsing adapters
- Source-grounded answers
- Monitoring tasks
- Research workflows

### Phase 6 — Personal services
- Calendar
- Email
- Contacts
- Reminders/tasks
- Notes
- Approval requirements for sends/edits/deletes

### Phase 7 — Automation and proactivity
- Time-based schedules
- Condition watches
- Event triggers
- Quiet hours
- Notification routing
- User-configurable proactive level

### Phase 8 — Voice
- Speech-to-text
- Text-to-speech
- Wake word
- Interruptible conversational voice
- Audio device selection

### Phase 9 — Environment awareness
- Screen understanding
- Application context
- Device telemetry
- Smart-home adapters
- Multi-device interfaces

### Phase 10 — SarahNode 1.0
- Unified memory + tools + automation + voice + awareness
- Stable permission model
- Plugin/adapter SDK
- Packaging, updates, backup/restore, diagnostics

## Safety model

Read-only operations may be auto-approved when their scope is granted. Writes, messages, purchases, destructive actions, security changes, system control, smart-home control, and similar side effects require explicit scopes and, depending on risk, user confirmation. The model never receives unrestricted authority merely because it generated a tool request.
