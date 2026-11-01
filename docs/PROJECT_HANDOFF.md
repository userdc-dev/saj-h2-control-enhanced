# Project handoff entrypoint

**The full authoritative developer guide has moved to [../DEVELOPER_HANDOFF.md](../DEVELOPER_HANDOFF.md). Read it first.**

This file is retained to preserve older links. The control project is **design-only**: no installed HA controller, battery quick-action implementation, schedules, or Modbus writes. The independent read-only monitor is [saj-h2-safe-enhanced](https://github.com/userdc-dev/saj-h2-safe-enhanced), whose complete monitoring handoff is [PROJECT_HANDOFF.md](https://github.com/userdc-dev/saj-h2-safe-enhanced/blob/main/PROJECT_HANDOFF.md).

Safety: never command mode 2 Backup or mode 3 Off-grid/Passive. Do not add active inverter control until a separately approved controlled hardware test and proven safe stop/readback. See the canonical handoff for the full plan and current work state.
