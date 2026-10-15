"""Examples for TTL grammar, limits, and exact diagnostics."""

import pytest

from zonevet.ttl import parse_ttl


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("300", 300),
        ("0", 0),
        ("0000000000", 0),
        ("0000000001", 1),
        ("1s", 1),
        ("10s", 10),
        ("1h30m", 5_400),
        ("2W", 1_209_600),
        ("1h1h", 7_200),
        ("1d1D", 172_800),
        ("1H30M", 5_400),
        ("0000000001s", 1),
        ("0000000001s0000000001s", 2),
        ("2147483647", 2_147_483_647),
        ("2147483647s", 2_147_483_647),
        ("2147483647s0s", 2_147_483_647),
    ],
)
def test_parse_ttl_accepts_supported_values(value: str, expected: int) -> None:
    assert parse_ttl(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "2147483648",
        "2147483648s",
        "2147483647s1s",
        "99999999999",
        "00000000001",
        "00000000001s",
        "1x",
        "1h30",
        "h1",
        "1hh",
        "1.5s",
        "1ss",
        "-1",
        "+1",
    ],
)
def test_parse_ttl_rejects_invalid_values_with_exact_error(value: str) -> None:
    with pytest.raises(ValueError) as error:
        parse_ttl(value)

    assert str(error.value) == f'invalid TTL "{value}"'


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("1 H", 'invalid TTL "1?H"'),
        ("١", 'invalid TTL "?"'),
        ("1\u00a0s", 'invalid TTL "1?s"'),
    ],
)
def test_parse_ttl_quotes_non_ascii_and_space_in_diagnostics(
    value: str, message: str
) -> None:
    with pytest.raises(ValueError) as error:
        parse_ttl(value)

    assert str(error.value) == message
