"""Read-only, fail-closed planning for a *single existing* SAJ TOU schedule.

No writes or network access here. The plan is bound to an exact saved slot
snapshot supplied by the client and verified against a fresh Modbus read in HA.
Weekend bits are deliberately blocked until individually verified on hardware.
"""
from dataclasses import dataclass
import re

DAY_BITS = {"Mon": 1, "Tue": 2, "Wed": 4, "Thu": 8, "Fri": 16}


class SchedulePreviewError(ValueError):
    pass


@dataclass(frozen=True)
class SlotValue:
    start: str
    end: str
    day_mask: int
    power_percent: int

    @classmethod
    def from_slot(cls, slot):
        return cls(slot.start, slot.end, slot.day_mask, slot.power_percent)


def _time_word(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
        raise SchedulePreviewError("Schedule time must be 24h HH:MM")
    hour, minute = map(int, value.split(":"))
    return (hour << 8) | minute


def _day_mask(days):
    if not isinstance(days, list) or not days or len(days) != len(set(days)):
        raise SchedulePreviewError("Choose at least one unique weekday")
    if any(day not in DAY_BITS for day in days):
        raise SchedulePreviewError(
            "Saturday/Sunday schedule writes not ready: individual day bits unverified")
    return sum(DAY_BITS[day] for day in days)


def preview_existing_slot(
    config, *, direction, slot_number, expected: SlotValue,
    new_start, new_end, days, power_percent,
):
    """Return raw target words and existing-word comparison, WITHOUT writing."""
    if direction not in ("charge", "discharge"):
        raise SchedulePreviewError("Invalid direction")
    if type(slot_number) is not int or not 1 <= slot_number <= 7:
        raise SchedulePreviewError("Slot must be numbered 1–7")
    if config.mode not in (0, 1) or config.fallback != 1:
        raise SchedulePreviewError("Unsupported mode or outside-window fallback")
    if config.charge_mask > 127 or config.discharge_mask > 127:
        raise SchedulePreviewError("Invalid enable masks")
    slots = config.charge_slots if direction == "charge" else config.discharge_slots
    current = slots[slot_number - 1]
    if not current.enabled:
        raise SchedulePreviewError("Only existing enabled slots may be previewed")
    if SlotValue.from_slot(current) != expected:
        raise SchedulePreviewError(
            "Inverter slot changed since draft was created; reload draft")
    start_word = _time_word(new_start)
    end_word = _time_word(new_end)
    if start_word == end_word:
        raise SchedulePreviewError("Start and end cannot be identical")
    # Overnight periods are not yet validated against eLEKeeper behaviour.
    if new_start > new_end:
        raise SchedulePreviewError("Overnight periods not yet verified")
    mask = _day_mask(days)
    if type(power_percent) is not int or not 1 <= power_percent <= 100:
        raise SchedulePreviewError("Power must be an integer from 1 to 100")
    packed = (mask << 8) | power_percent
    raw = [start_word, end_word, packed]
    old = [*map(_time_word, (current.start, current.end)),
           (current.day_mask << 8) | current.power_percent]
    address = (0x3606 if direction == "charge" else 0x361B) + 3 * (slot_number - 1)
    return {
        "status": "SCHEDULE_DRY_RUN_ONLY",
        "write_sent": False,
        "direction": direction,
        "slot": slot_number,
        "register_addresses": [address, address + 1, address + 2],
        "existing_words": old,
        "proposed_words": raw,
        "change_needed": raw != old,
        "proposed_display_watts_estimated": 99 * power_percent,
        "weekday_mask": mask,
        "inverter_mode": config.mode,
        "message": (
            "Validated existing slot against fresh double-read. "
            "Schedule writes are NOT implemented. Raw words are for review ONLY."
        ),
    }
