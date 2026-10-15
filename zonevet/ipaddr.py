"""IPv4 and IPv6 address parsers with deterministic canonicalization."""

from collections.abc import Sequence

from zonevet.text import quote


def _invalid_ipv4(value: str) -> ValueError:
    return ValueError(f"invalid IPv4 address {quote(value)}")


def _invalid_ipv6(value: str) -> ValueError:
    return ValueError(f"invalid IPv6 address {quote(value)}")


def parse_ipv4(value: str) -> str:
    """Validate and return a canonical dotted-decimal IPv4 address."""
    parts = value.split(".")
    if len(parts) != 4:
        raise _invalid_ipv4(value)

    octets: list[int] = []
    for part in parts:
        if not part or len(part) > 3 or any(character < "0" or character > "9" for character in part):
            raise _invalid_ipv4(value)
        if len(part) > 1 and part[0] == "0":
            raise _invalid_ipv4(value)
        number = int(part)
        if number > 255:
            raise _invalid_ipv4(value)
        octets.append(number)
    return ".".join(str(octet) for octet in octets)


def _parse_ipv6_side(value: str, original: str) -> tuple[list[int], bool]:
    if not value:
        return [], False

    words: list[int] = []
    parts = value.split(":")
    for index, part in enumerate(parts):
        if not part:
            raise _invalid_ipv6(original)
        if "." in part:
            if index != len(parts) - 1:
                raise _invalid_ipv6(original)
            try:
                address = parse_ipv4(part)
            except ValueError:
                raise _invalid_ipv6(original) from None
            octets = [int(octet) for octet in address.split(".")]
            words.extend((octets[0] * 256 + octets[1], octets[2] * 256 + octets[3]))
            return words, True
        if not 1 <= len(part) <= 4 or any(
            character not in "0123456789abcdefABCDEF" for character in part
        ):
            raise _invalid_ipv6(original)
        words.append(int(part, 16))
    return words, False


def parse_ipv6(value: str) -> tuple[int, ...]:
    """Parse an IPv6 address into eight 16-bit groups.

    A trailing dotted-decimal IPv4 address is represented by its two equivalent
    hexadecimal groups.
    """
    if not value or "%" in value or value.count("::") > 1:
        raise _invalid_ipv6(value)

    compressed = "::" in value
    if compressed:
        left_text, right_text = value.split("::", 1)
        left, left_has_ipv4 = _parse_ipv6_side(left_text, value)
        right, right_has_ipv4 = _parse_ipv6_side(right_text, value)
        if left_has_ipv4 or (right_has_ipv4 and not right_text):
            raise _invalid_ipv6(value)
        words = left + right
        if len(words) >= 8:
            raise _invalid_ipv6(value)
        words = left + ([0] * (8 - len(words))) + right
    else:
        if value.startswith(":") or value.endswith(":"):
            raise _invalid_ipv6(value)
        words, _has_ipv4 = _parse_ipv6_side(value, value)
        if len(words) != 8:
            raise _invalid_ipv6(value)

    if len(words) != 8:
        raise _invalid_ipv6(value)
    return tuple(words)


def format_ipv6(groups: Sequence[int]) -> str:
    """Format eight IPv6 groups using the first longest compressible zero run."""
    if len(groups) != 8 or any(not isinstance(group, int) or not 0 <= group <= 0xFFFF for group in groups):
        raise ValueError("expected eight IPv6 groups")

    best_start = -1
    best_length = 1
    start = 0
    while start < len(groups):
        if groups[start] != 0:
            start += 1
            continue
        end = start
        while end < len(groups) and groups[end] == 0:
            end += 1
        length = end - start
        if length > best_length:
            best_start = start
            best_length = length
        start = end

    rendered = [format(group, "x") for group in groups]
    if best_start == -1:
        return ":".join(rendered)

    before = ":".join(rendered[:best_start])
    after = ":".join(rendered[best_start + best_length :])
    return f"{before}::{after}"
