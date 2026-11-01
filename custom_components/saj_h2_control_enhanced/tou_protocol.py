"""Decode read-only SAJ H2 Time-of-Use registers. No Modbus writes.

Validated on owner's inverter: mode 0/1; 7+7 slot blocks; discharge
raw 100=9900W, 98=9702W, 50=4950W; weekday raw mask 4=Wednesday.
Other weekday bits and charge power scaling remain unverified.
"""
from dataclasses import dataclass

CHARGE_START, CHARGE_COUNT = 0x3604, 23
DISCHARGE_START, DISCHARGE_COUNT = 0x361B, 21
MODE_ADDR, FALLBACK_ADDR = 0x3647, 0x365F
SLOTS = 7


class InvalidTOUData(ValueError):
    """Invalid or unsupported readback."""


@dataclass(frozen=True)
class Slot:
    number: int
    enabled: bool
    start: str
    end: str
    day_mask: int
    power_percent: int

    def as_dict(self, *, discharge=False):
        result = {
            "slot": self.number,
            "start": self.start,
            "end": self.end,
            "weekday_mask_raw": self.day_mask,
            "power_percent_raw": self.power_percent,
        }
        if discharge:
            result["power_watts_saj_display"] = self.power_percent * 99
        else:
            result["power_watts_saj_display"] = None
        return result


@dataclass(frozen=True)
class Config:
    mode: int
    fallback: int
    charge_mask: int
    discharge_mask: int
    charge_slots: tuple[Slot, ...]
    discharge_slots: tuple[Slot, ...]

    @property
    def mode_text(self):
        return {0: "Self-consumption", 1: "Time-of-use", 2: "Backup (unsupported)",
                3: "Off-grid / Passive (unsupported)"}.get(self.mode, "Unknown")

    @property
    def fallback_text(self):
        return {0: "Standby", 1: "Self-consumption"}.get(self.fallback, "Unknown")

    def summary(self, direction):
        slots = self.charge_slots if direction == "charge" else self.discharge_slots
        return [slot.as_dict(discharge=direction == "discharge")
                for slot in slots if slot.enabled]


def _check_word(value):
    if type(value) is not int or value < 0 or value > 65535:
        raise InvalidTOUData("Invalid unsigned Modbus register")
    return value


def _clock(word):
    hour, minute = word >> 8, word & 255
    if hour > 23 or minute > 59:
        raise InvalidTOUData("Invalid 24-hour schedule time")
    return f"{hour:02d}:{minute:02d}"


def _decode_slots(words, enable):
    slots = []
    for i in range(7):
        start, end, mixed = words[i * 3:i * 3 + 3]
        enabled = bool(enable & (1 << i))
        # Disabled slots can retain stale/invalid register contents.
        # Never let those block real active schedule readback.
        if enabled:
            start_text, end_text = _clock(start), _clock(end)
        else:
            try:
                start_text, end_text = _clock(start), _clock(end)
            except InvalidTOUData:
                start_text, end_text = "unknown", "unknown"
        power = mixed & 255
        if enabled and power > 100:
            raise InvalidTOUData("Active schedule power exceeds 100%")
        slots.append(Slot(
            number=i + 1,
            enabled=enabled,
            start=start_text, end=end_text,
            day_mask=mixed >> 8,
            power_percent=power,
        ))
    return tuple(slots)


def decode_config(charge, discharge, mode, fallback):
    if len(charge) != 23 or len(discharge) != 21:
        raise InvalidTOUData("Incomplete TOU register block")
    charge = tuple(_check_word(v) for v in charge)
    discharge = tuple(_check_word(v) for v in discharge)
    mode, fallback = _check_word(mode), _check_word(fallback)
    charge_mask, discharge_mask = charge[:2]
    if charge_mask > 127 or discharge_mask > 127:
        raise InvalidTOUData("Unexpected schedule enable mask")
    return Config(
        mode=mode, fallback=fallback, charge_mask=charge_mask,
        discharge_mask=discharge_mask,
        charge_slots=_decode_slots(charge[2:], charge_mask),
        discharge_slots=_decode_slots(discharge, discharge_mask),
    )
