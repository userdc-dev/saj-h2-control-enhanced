"""Initial design-only safety tests. No network or device access."""
BLOCKED_MODE_CODES = frozenset((2, 3))
ALLOWED_READ_MODE_CODES = frozenset((0, 1, 2, 3))

def is_permitted_future_mode(mode):
    return type(mode) is int and mode in (0, 1)

def valid_proposed_duration(minutes):
    return type(minutes) is int and 1 <= minutes <= 120

assert not is_permitted_future_mode(2)
assert not is_permitted_future_mode(3)
assert not is_permitted_future_mode(-1)
assert not is_permitted_future_mode(None)
assert is_permitted_future_mode(0)
assert is_permitted_future_mode(1)
assert valid_proposed_duration(30)
assert not valid_proposed_duration(0)
assert not valid_proposed_duration(999)
assert not valid_proposed_duration(True)
print('Read-only scaffold safety checks passed (no device controls implemented).')
