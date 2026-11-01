# Project handoff entrypoint

**Canonical up-to-date developer guide:** [DEVELOPER_HANDOFF.md](../DEVELOPER_HANDOFF.md). **Read it first.** It covers current writable controls, source architecture, exact Modbus registers, simulated-vs-live test results, recovery and the latest release.

**Full historical diary:** [DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md](DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md). Early statements there claiming the project is planning-only or has no live controls are **obsolete historical milestones**.

**Independent safe monitor:** [saj-h2-safe-enhanced](https://github.com/userdc-dev/saj-h2-safe-enhanced). This is a separate read-only component; its code and the existing SAJ Energy dashboard must not be altered by this repository.

**Current state:** An installed Home Assistant control integration supports live mode switching, schedule plan/apply actions, and Outside TOU window fallback controls. The card also now shows read-only SAJ Energy–style graphics/table from existing Safe Monitor sensors. Actual mode switching has been confirmed on hardware; other controls have varying levels of field verification documented in the canonical handover. Offline CI is not proof of physical inverter success.

**Security/safety:** No mode 2/3 writes, no battery protection or export-setting changes, no automatic retries after ambiguous writes, explicit confirmation for Standby, preserve the separate read-only monitor. Call the SAJ mobile app **elekeeper**.

**Start here to continue development:** [../DEVELOPER_HANDOFF.md](../DEVELOPER_HANDOFF.md).
