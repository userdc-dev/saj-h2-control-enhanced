"""Decode read-only SAJ H2 Time-of-Use registers. No Modbus writes.

Validated on owner's inverter: mode 0/1; 7+7 slot blocks; discharge
discharge raw 100=9900W, 98=9702W, 50=4950W; charging raw 50=4950W.
Wednesday weekday bit 4 and Friday bit 16 are verified. The remaining
weekday bits and charge-side scaling beyond raw 50 are not yet verified.
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
            "weekday_verified": {4: "Wednesday", 16: "Friday",
                                 20: "Wednesday, Friday"}.get(self.day_mask, "Unverified"),
            "power_percent_raw": self.power_percent,
        }
        if discharge:
            result["power_watts_saj_display"] = self.power_percent * 99
            result["power_conversion_verified"] = True
        else:
            # Charge power has only one paired eLEKeeper/Modbus test so far.
            result["power_watts_saj_display"] = 4950 if self.power_percent == 50 else None
            result["power_conversion_verified"] = self.power_percent == 50
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



def active_signature(config: Config):
    """Only actual enabled slots count as active schedule changes.

    Disabled slots may retain old times/power: their values do not mean
    the eLEKeeper schedule changed.
    """
    return (
        config.mode, config.fallback, config.charge_mask,
        config.discharge_mask,
        tuple(s for s in config.charge_slots if s.enabled),
        tuple(s for s in config.discharge_slots if s.enabled),
    )


def describe_changes(previous: Config, current: Config) -> tuple[str, ...]:
    """Human-readable device-readback changes, never presumed HA commands."""
    differences = []
    if previous.mode != current.mode:
        differences.append(f"Mode: {previous.mode_text} → {current.mode_text}")
    if previous.fallback != current.fallback:
        differences.append(
            f"Outside TOU: {previous.fallback_text} → {current.fallback_text}")
    for direction in ("charge", "discharge"):
        a = previous.charge_slots if direction == "charge" else previous.discharge_slots
        b = current.charge_slots if direction == "charge" else current.discharge_slots
        for before, after in zip(a, b):
            before_value = before if before.enabled else None
            after_value = after if after.enabled else None
            if before_value != after_value:
                differences.append(f"{direction.title()} slot {after.number} changed")
    return tuple(differences)
