"""Experimental SAJ H2 TOU readback decoder. PURE PYTHON; NO WRITES.

Addresses/packing derived from upstream stanus74/home-assistant-saj-h2-modbus
modbus_readers.py and require verification against the user's SAJ eLEKeeper UI.

Three Modbus holding-register read blocks:
  0x3604 x 23: charge/discharge enable masks + 7 charge slots
  0x361B x 21: 7 discharge slots
  0x3647 x 1 : operating mode (read only)
  0x365F x 1 : TOU outside-window fallback (0 standby, 1 self-use)

Each slot contains start and end words as HH<<8 | MM and one combined
word high-byte=day mask, low-byte=power PERCENT (NOT watts).
The precise weekday bit ordering and power scaling to W are UNVERIFIED.
"""
from dataclasses import dataclass

CHARGE_START = 0x3604
CHARGE_COUNT = 23
DISCHARGE_START = 0x361B
DISCHARGE_COUNT = 21
MODE_ADDR = 0x3647
FALLBACK_ADDR = 0x365F
SLOTS = 7

class UnverifiedMapping(ValueError):
    pass

@dataclass(frozen=True)
class Slot:
    index: int
    enabled: bool
    start: str
    end: str
    day_mask_raw: int
    power_percent_raw: int
    # Do not add watts/day name until reconciled against the official SAJ app.

@dataclass(frozen=True)
class DeviceTOU:
    mode_raw: int
    fallback_raw: int
    charge_enable_mask: int
    discharge_enable_mask: int
    charge_slots: tuple[Slot, ...]
    discharge_slots: tuple[Slot, ...]
    mapping_verified: bool = False  # NEVER assume the upstream schema matches.
    def operating_mode_label(self):
        return {0: "Self-consumption", 1: "Time-of-use"}.get(
            self.mode_raw, "Other/unsupported")
    def fallback_label(self):
        return {0: "Standby", 1: "Self-consumption"}.get(
            self.fallback_raw, "Unknown/unsupported")

def _word(value, label):
    if type(value) is not int or not 0 <= value <= 65535:
        raise UnverifiedMapping(f"{label}: invalid unsigned 16-bit word")
    return value

def _time(word):
    hours = word >> 8
    minutes = word & 255
    if hours > 23 or minutes > 59:
        raise UnverifiedMapping(f"Invalid time packing: 0x{word:04X}")
    return f"{hours:02d}:{minutes:02d}"

def _slots(words, *, offset, mask):
    out = []
    for i in range(SLOTS):
        start, end, combined = words[offset + i*3:offset + i*3+3]
        out.append(Slot(
            index=i+1,
            enabled=bool(mask & (1 << i)),
            start=_time(start),
            end=_time(end),
            day_mask_raw=combined >> 8,
            power_percent_raw=combined & 255,
        ))
    return tuple(out)

def decode_tou(charge_words, discharge_words, mode_word, fallback_word):
    """Decode independent read-only blocks; errors prevent fake default values."""
    if len(charge_words) != CHARGE_COUNT or len(discharge_words) != DISCHARGE_COUNT:
        raise UnverifiedMapping("Wrong TOU read block length")
    charge_words = tuple(_word(x, "charge") for x in charge_words)
    discharge_words = tuple(_word(x, "discharge") for x in discharge_words)
    mode = _word(mode_word, "mode")
    fallback = _word(fallback_word, "fallback")
    charge_mask, discharge_mask = charge_words[:2]
    if charge_mask & ~0x7F or discharge_mask & ~0x7F:
        raise UnverifiedMapping("Unknown enable bits; do not infer active slots")
    return DeviceTOU(
        mode_raw=mode,
        fallback_raw=fallback,
        charge_enable_mask=charge_mask,
        discharge_enable_mask=discharge_mask,
        charge_slots=_slots(charge_words, offset=2, mask=charge_mask),
        discharge_slots=_slots(discharge_words, offset=0, mask=discharge_mask),
    )

def diff_device_configs(before: DeviceTOU, after: DeviceTOU):
    """Detect app/external setting changes WITHOUT writing or auto-acknowledging."""
    differences = {}
    for field in ("mode_raw", "fallback_raw", "charge_enable_mask",
                  "discharge_enable_mask", "charge_slots", "discharge_slots"):
        a, b = getattr(before, field), getattr(after, field)
        if a != b:
            differences[field] = {"previous": a, "current": b}
    return differences
