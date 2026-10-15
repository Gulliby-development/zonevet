"""Examples for address validation and canonical rendering."""

import pytest

from zonevet.ipaddr import format_ipv6, parse_ipv4, parse_ipv6


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.0.2.1", "192.0.2.1"),
        ("0.0.0.0", "0.0.0.0"),
        ("255.255.255.255", "255.255.255.255"),
        ("1.2.3.4", "1.2.3.4"),
        ("10.0.255.1", "10.0.255.1"),
        ("9.8.7.6", "9.8.7.6"),
    ],
)
def test_parse_ipv4_accepts_four_canonical_decimal_octets(value: str, expected: str) -> None:
    assert parse_ipv4(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "192.0.2.01",
        "256.1.1.1",
        "1.2.3",
        "",
        "1.2.3.4.5",
        "1..2.3",
        ".1.2.3",
        "1.2.3.",
        "+1.2.3.4",
        "-1.2.3.4",
        "1.2.3.256",
        "00.0.0.0",
        "1.2.3.٠",
    ],
)
def test_parse_ipv4_rejects_invalid_forms_with_exact_message(value: str) -> None:
    with pytest.raises(ValueError) as error:
        parse_ipv4(value)

    assert str(error.value) == f'invalid IPv4 address "{value.replace("٠", "?")}"'


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "2001:0db8:0000:0000:0000:0000:0000:0001",
            "2001:db8::1",
        ),
        ("::", "::"),
        ("1:0:0:2:0:0:0:3", "1:0:0:2::3"),
        ("1:0:0:2:0:0:3:4", "1::2:0:0:3:4"),
        ("1:0:2:3:4:5:6:7", "1:0:2:3:4:5:6:7"),
        ("::ffff:192.0.2.1", "::ffff:c000:201"),
        ("1:2:3:4:5:6:7::", "1:2:3:4:5:6:7:0"),
        ("1:2:3:4:5:6:1.2.3.4", "1:2:3:4:5:6:102:304"),
        ("1:2:3:4:5:6:7:8", "1:2:3:4:5:6:7:8"),
        ("0:0:1:2:3:4:5:6", "::1:2:3:4:5:6"),
        ("1:2:3:4:5:6:0:0", "1:2:3:4:5:6::"),
        ("1:2:3:4:5:6:0:7", "1:2:3:4:5:6:0:7"),
        (
            "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
            "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
        ),
        ("0:0:0:0:0:0:0:1", "::1"),
        ("::192.0.2.1", "::c000:201"),
    ],
)
def test_parse_ipv6_and_format_ipv6_match_canonical_examples(value: str, expected: str) -> None:
    groups = parse_ipv6(value)

    assert len(groups) == 8
    assert all(0 <= group <= 0xFFFF for group in groups)
    assert format_ipv6(groups) == expected


@pytest.mark.parametrize(
    "value",
    [
        "1::2::3",
        ":1::2",
        "1:2:3:4:5:6:7",
        "12345::",
        "::1%eth0",
        "1:::2",
        "",
        "1:2:3:4:5:6:7:8:9",
        ":1:2:3:4:5:6:7:8",
        "1:2:3:4:5:6:7:8:",
        ":::",
        "1:2:3:4:5:6:192.0.2.1:192.0.2.1",
        "1:2:3:4:5::192.0.2.1:192.0.2.1",
        "1:2:3:4:5:6:7:gggg",
        "1.2.3.4::",
        "::192.0.2.01",
        "1:2:3:4:5:6:7:12345",
    ],
)
def test_parse_ipv6_rejects_invalid_forms_with_exact_message(value: str) -> None:
    with pytest.raises(ValueError) as error:
        parse_ipv6(value)

    assert str(error.value) == f'invalid IPv6 address "{value}"'


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        ((0, 0, 0, 0, 0, 0, 0, 0), "::"),
        ((1, 0, 0, 2, 0, 0, 0, 3), "1:0:0:2::3"),
        ((1, 0, 0, 2, 0, 0, 3, 4), "1::2:0:0:3:4"),
        ((0, 0, 1, 2, 3, 4, 5, 6), "::1:2:3:4:5:6"),
        ((1, 2, 3, 4, 5, 6, 0, 0), "1:2:3:4:5:6::"),
        ((1, 0, 2, 3, 4, 5, 6, 7), "1:0:2:3:4:5:6:7"),
        ((1, 2, 3, 4, 5, 6, 7, 0), "1:2:3:4:5:6:7:0"),
    ],
)
def test_format_ipv6_compresses_only_longest_zero_runs(
    groups: tuple[int, ...], expected: str
) -> None:
    assert format_ipv6(groups) == expected


@pytest.mark.parametrize(
    "groups",
    [
        (),
        (0, 0, 0, 0, 0, 0, 0),
        (0, 0, 0, 0, 0, 0, 0, 0, 0),
        (-1, 0, 0, 0, 0, 0, 0, 0),
        (65536, 0, 0, 0, 0, 0, 0, 0),
    ],
)
def test_format_ipv6_requires_eight_unsigned_16_bit_groups(groups: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="^expected eight IPv6 groups$"):
        format_ipv6(groups)
