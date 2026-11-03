"""Read-only planner for future, bounded wholesale-VPP quick commands.

IMPORTANT: This module MUST NOT write registers or arm a timer. A standard
SAJ H2 TOU slot is weekly recurring; a one-off five-minute dispatch requires
durable restoration across HA restarts, guaranteed inverter cleanup and tested
100% charging. The existing write engine explicitly disallows automatic
rollback on uncertain Modbus replies, so real quick charge/discharge is
NOT safe to expose yet. Preview eligibility and hazards transparently.
"""
from __future__ import annotations

from datetime import datetime, timedelta

DURATIONS = (5, 10, 60)
DIRECTIONS = ("charge", "discharge")
MAX_RAW_PERCENT = 100
# Individual Saturday/Sunday bits are not paired with on-device evidence.
VERIFIED_SINGLE_DAY_BITS = (1, 2, 4, 8, 16)


def _minutes(text):
    """Read already-validated HH:MM from an enabled TOU slot."""
    if not isinstance(text, str):
        return None
    try:
        hh, mm = (int(s) for s in text.split(":"))
    except (TypeError, ValueError):
        return None
    if len(text) != 5 or not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return hh * 60 + mm


def preview_dispatch(config, *, direction, duration_minutes, now, soc=None):
    """Describe a prospective schedule, but never return an executable grant.

    config is the read-only double-verified tou_protocol.Config snapshot.
    now is the HA-local timezone-aware instant, not browser time.
    """
    if direction not in DIRECTIONS:
        raise ValueError("Direction must be charge or discharge")
    if type(duration_minutes) is not int or duration_minutes not in DURATIONS:
        raise ValueError("Supported durations are 5, 10 and 60 minutes")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Home Assistant local time must be timezone-aware")

    reasons = []
    warnings = []
    # Never program a schedule for the past or for an unverified weekend.
    begin = now.replace(second=0, microsecond=0) + timedelta(minutes=3)
    finish = begin + timedelta(minutes=duration_minutes)
    if begin.date() != finish.date():
        reasons.append("This command would cross midnight; overnight TOU timing is unverified")
    if begin.utcoffset() != finish.utcoffset():
        reasons.append("This interval crosses a daylight-saving time change")
    weekday = begin.weekday()
    bit = (1 << weekday) if weekday < 7 else 0
    if bit not in VERIFIED_SINGLE_DAY_BITS:
        reasons.append("Individual Saturday/Sunday TOU day bits are not yet hardware-verified")

    if config.mode not in (0, 1):
        reasons.append("Unsupported current inverter mode")
    if config.fallback != 1:
        reasons.append(
            "Outside TOU windows must already be Self-consumption "
            "(changing fallback automatically is not authorized)")
    if not (0 <= config.charge_mask <= 127 and 0 <= config.discharge_mask <= 127):
        reasons.append("Unexpected TOU schedule enable mask")

    selected = config.charge_slots if direction == "charge" else config.discharge_slots
    free = next((s.number for s in selected if not s.enabled), None)
    if free is None:
        reasons.append("All seven "+direction+" schedule slots are occupied")
    begin_min = begin.hour*60 + begin.minute
    end_min = finish.hour*60 + finish.minute
    if begin.date() == finish.date():
        for kind, slots in (("charge", config.charge_slots),
                            ("discharge", config.discharge_slots)):
            for slot in slots:
                if not slot.enabled:
                    continue
                start_min = _minutes(slot.start)
                stop_min = _minutes(slot.end)
                # A weekly slot crossing midnight can spill into the
                # requested day from the previous day. Until overnight
                # semantics are field-verified, no VPP preview may treat
                # such a slot as safely non-overlapping, even when the
                # slot's weekday mask differs from today's.
                if start_min is None or stop_min is None or start_min >= stop_min:
                    reasons.append(
                        f"Active {kind} slot {slot.number} has an unverified "
                        "or overnight time; possible cross-day conflict"
                    )
                elif slot.day_mask & bit and begin_min < stop_min and start_min < end_min:
                    reasons.append(
                        f"Existing {kind} slot {slot.number} overlaps the requested interval"
                    )

    if type(soc) not in (int, float) or not 0 <= soc <= 100:
        reasons.append("Recent battery state of charge is unavailable")
    elif direction == "charge" and soc >= 95:
        reasons.append("Battery is already at or above 95% SOC")
    elif direction == "discharge" and soc <= 10:
        reasons.append("Battery is at or below the 10% reserve")

    warnings += [
        "Raw TOU 100% is a requested limit, not guaranteed inverter output.",
        "Full-power charging at raw 100% is not yet field-verified on this firmware.",
        "A programmed TOU slot is WEEKLY RECURRING and must be safely cleared.",
        "An HA restart, network loss, VPP intervention, or partial write could "
        "leave a repeating schedule. A persistent watchdog and verified "
        "restoration are prerequisites for enabling these buttons.",
        "BMS temperature, grid export caps and VPP compliance must be respected.",
    ]
    return {
        "status": "VPP_PREFLIGHT_ONLY",
        "write_sent": False,
        "live_activation_supported": False,
        "can_start": False,
        "preflight_passed": not reasons,
        "direction": direction,
        "duration_minutes": duration_minutes,
        "requested_power_percent_raw": MAX_RAW_PERCENT,
        "planned_start_local": begin.isoformat(),
        "planned_end_local": finish.isoformat(),
        "proposed_slot": free,
        "day_mask_raw": bit if bit in VERIFIED_SINGLE_DAY_BITS else None,
        "existing_mode": config.mode_text,
        "outside_window_mode": config.fallback_text,
        "blockers": reasons,
        "warnings": warnings,
        "next_step": (
            "Read-only preview. A tested durable watchdog, safe recovery,"
            " current battery telemetry and inverter-specific 100% charging"
            " verification are required before live timed dispatch is enabled."
        ),
    }
