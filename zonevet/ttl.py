"""TTL grammar and numeric conversion."""

from zonevet.text import quote

_MAX_TTL = 2_147_483_647
_UNITS = {"w": 604_800, "d": 86_400, "h": 3_600, "m": 60, "s": 1}


def parse_ttl(value: str) -> int:
    """Parse decimal seconds or a sequence of digit/unit pairs."""
    if not value:
        raise ValueError(f"invalid TTL {quote(value)}")

    if all("0" <= character <= "9" for character in value):
        if len(value) > 10:
            raise ValueError(f"invalid TTL {quote(value)}")
        result = int(value)
    else:
        index = 0
        result = 0
        while index < len(value):
            start = index
            while index < len(value) and "0" <= value[index] <= "9":
                index += 1
            digit_count = index - start
            if not 1 <= digit_count <= 10 or index == len(value):
                raise ValueError(f"invalid TTL {quote(value)}")
            unit = value[index].lower()
            if unit not in _UNITS:
                raise ValueError(f"invalid TTL {quote(value)}")
            result += int(value[start:index]) * _UNITS[unit]
            index += 1

    if result > _MAX_TTL:
        raise ValueError(f"invalid TTL {quote(value)}")
    return result
