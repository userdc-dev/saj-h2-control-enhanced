# Quick context for a future assistant

- Project purpose: add *opt-in* charge/discharge quick actions (duration in minutes), time-of-use weekday schedules, and cancel/watchdog features, eventually shown in the space freed underneath `saj-energy/live`.
- Crucial split: `userdc-dev/saj-h2-safe-enhanced` MUST remain read-only. Put all future writable development in a separate repo / integration.
- User's strict operating restrictions: Never transmit operating mode 2 Backup nor 3 Off-grid/Passive; mode 3 interpretation has ambiguity across firmware/upstream. Avoid changes to BMS/reserve/voltage protections. Do not build unattended control until read-back and fail-safe stop paths are validated.
- User prefers one short action/SSH command at a time and complete replacement code/YAML files, not partial snippets.
- Monitoring baseline: SAJ H2 10 kW AC, 40.00 kWh battery according to SAJ app, 13.2 kWp solar; live readings ~10 seconds. Capacity percentage is not necessarily usable energy.
- Home Assistant dashboard: `saj-energy/live` live flow on left, 24-hour power graph on right. Old second row containing oversized battery SOC gauge, battery card and PV inputs was intentionally removed from the *read-only* GitHub YAML to make room for future controls. Those control widgets do not currently exist.
- Current status of this repo scaffold: documents and tests only. It must NOT include working inverter writes. Do not pretend actions work.
- In future use the authoritative read-only handoff: https://github.com/userdc-dev/saj-h2-safe-enhanced/blob/main/PROJECT_HANDOFF.md
- First next step after repo creation: commit this scaffold, make an inert mock compact dashboard section, verify mode and BMS details, design testable timer state machine. Implementing writes requires separate owner authorization after safety testing.
