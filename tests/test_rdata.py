"""Handwritten examples for resource-data validation and canonical rendering."""

import pytest

from zonevet.lexer import Token
from zonevet.rdata import SOAFields, parse_rdata

ORIGIN = "example.com."


def _token(value: str, *, line: int = 1, quoted: bool = False) -> Token:
    return Token(value, line, quoted)


_UTF8_120 = (
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
    "éééééééééé"
)
_UTF8_127 = _UTF8_120 + "ééééééé"
_UTF8_128 = _UTF8_120 + "éééééééé"
_UTF8_255_BYTES = _UTF8_127 + "a"


@pytest.mark.parametrize(
    ("rtype", "tokens", "values", "canonical"),
    [
        ("a", (_token("192.0.2.53"),), ("192.0.2.53",), "192.0.2.53"),
        ("aaaa", (_token("2001:0db8:0000:0000:0000:0000:0000:0001"),), ("2001:db8::1",), "2001:db8::1"),
        ("cname", (_token("WWW", line=4),), ("www.example.com.",), "www.example.com."),
        ("NS", (_token("NS1"),), ("ns1.example.com.",), "ns1.example.com."),
        ("PTR", (_token("host.example.net."),), ("host.example.net.",), "host.example.net."),
        ("MX", (_token("0"), _token("MAIL")), (0, "mail.example.com."), "0 mail.example.com."),
        ("MX", (_token("65535"), _token(".")), (65535, "."), "65535 ."),
        ("SRV", (_token("0"), _token("65535"), _token("65535"), _token("sip")), (0, 65535, 65535, "sip.example.com."), "0 65535 65535 sip.example.com."),
        ("TXT", (_token("v=spf1 mx -all", quoted=True), _token("ok")), ("v=spf1 mx -all", "ok"), '"v=spf1 mx -all" "ok"'),
        (
            "SOA",
            (
                _token("NS1"), _token("Hostmaster"), _token("4294967295"), _token("1h30m"),
                _token("2W"), _token("2147483647"), _token("0"),
            ),
            ("ns1.example.com.", "hostmaster.example.com.", 4294967295, 5400, 1209600, 2147483647, 0),
            "ns1.example.com. hostmaster.example.com. 4294967295 5400 1209600 2147483647 0",
        ),
        (
            "SOA",
            (
                _token("ns"), _token("hostmaster"), _token("0"), _token("0"),
                _token("0"), _token("0"), _token("0"),
            ),
            ("ns.example.com.", "hostmaster.example.com.", 0, 0, 0, 0, 0),
            "ns.example.com. hostmaster.example.com. 0 0 0 0 0",
        ),
    ],
)
def test_parse_rdata_canonicalizes_every_supported_type(
    rtype: str,
    tokens: tuple[Token, ...],
    values: tuple[str | int, ...],
    canonical: str,
) -> None:
    parsed = parse_rdata(rtype, tokens, ORIGIN)

    assert parsed.rtype == rtype.upper()
    assert parsed.values == values
    assert parsed.canonical == canonical


@pytest.mark.parametrize(
    ("rtype", "tokens", "message"),
    [
        ("A", (), 'expected "A ADDRESS"'),
        ("A", (_token("192.0.2.1"), _token("192.0.2.2")), 'expected "A ADDRESS"'),
        ("AAAA", (), 'expected "AAAA ADDRESS"'),
        ("CNAME", (), 'expected "CNAME NAME"'),
        ("CNAME", (_token("one"), _token("two")), 'expected "CNAME NAME"'),
        ("NS", (), 'expected "NS NAME"'),
        ("PTR", (_token("one"), _token("two")), 'expected "PTR NAME"'),
        ("MX", (_token("10"),), 'expected "MX PREFERENCE NAME"'),
        (
            "MX",
            (_token("10"), _token("mail"), _token("extra")),
            'expected "MX PREFERENCE NAME"',
        ),
        ("SRV", (), 'expected "SRV PRIORITY WEIGHT PORT TARGET"'),
        (
            "SRV",
            (_token("1"), _token("2"), _token("3"), _token("target"), _token("extra")),
            'expected "SRV PRIORITY WEIGHT PORT TARGET"',
        ),
        ("TXT", (), 'expected "TXT STRING..."'),
        (
            "SOA",
            (_token("ns"), _token("hostmaster"), _token("1"), _token("2"), _token("3"), _token("4")),
            'expected "SOA MNAME RNAME SERIAL REFRESH RETRY EXPIRE MINIMUM"',
        ),
    ],
)
def test_parse_rdata_checks_arity_with_exact_type_specific_errors(
    rtype: str, tokens: tuple[Token, ...], message: str
) -> None:
    with pytest.raises(ValueError) as error:
        parse_rdata(rtype, tokens, ORIGIN)

    assert str(error.value) == message


@pytest.mark.parametrize(
    ("rtype", "tokens", "message"),
    [
        (
            "MX",
            (_token("70000"), _token("bad/name")),
            'invalid number "70000" (expected 0 to 65535)',
        ),
        (
            "MX",
            (_token("12345678901"), _token("mail")),
            'invalid number "12345678901" (expected 0 to 65535)',
        ),
        (
            "MX",
            (_token("+1"), _token("mail")),
            'invalid number "+1" (expected 0 to 65535)',
        ),
        (
            "SRV",
            (_token("65536"), _token("70000"), _token("70000"), _token("bad/name")),
            'invalid number "65536" (expected 0 to 65535)',
        ),
        (
            "SRV",
            (_token("0"), _token("65536"), _token("0"), _token("target")),
            'invalid number "65536" (expected 0 to 65535)',
        ),
        (
            "SRV",
            (_token("0"), _token("0"), _token("65536"), _token("target")),
            'invalid number "65536" (expected 0 to 65535)',
        ),
        (
            "SOA",
            (
                _token("ns"),
                _token("hostmaster"),
                _token("4294967296"),
                _token("not-a-ttl"),
                _token("1"),
                _token("1"),
                _token("1"),
            ),
            'invalid number "4294967296" (expected 0 to 4294967295)',
        ),
        (
            "SOA",
            (
                _token("ns"),
                _token("hostmaster"),
                _token("12345678901"),
                _token("1"),
                _token("1"),
                _token("1"),
                _token("1"),
            ),
            'invalid number "12345678901" (expected 0 to 4294967295)',
        ),
    ],
)
def test_numeric_rdata_rejects_overflow_and_malformed_values_left_to_right(
    rtype: str, tokens: tuple[Token, ...], message: str
) -> None:
    with pytest.raises(ValueError) as error:
        parse_rdata(rtype, tokens, ORIGIN)

    assert str(error.value) == message


def test_name_references_keep_source_spelling_line_and_field() -> None:
    parsed = parse_rdata("CNAME", (_token("WWW", line=8),), ORIGIN)

    assert parsed.name_references[0].raw == "WWW"
    assert parsed.name_references[0].resolved == "www.example.com."
    assert parsed.name_references[0].line == 8
    assert parsed.name_references[0].field == "target"
    assert parsed.raw_names == ("WWW",)
    assert parsed.targets == ("www.example.com.",)


def test_soa_exposes_typed_fields_and_both_explicit_name_references() -> None:
    parsed = parse_rdata(
        "SOA",
        (
            _token("NS1", line=9),
            _token("Hostmaster", line=9),
            _token("1"),
            _token("1h"),
            _token("15m"),
            _token("2w"),
            _token("300"),
        ),
        ORIGIN,
    )

    assert parsed.soa == SOAFields(
        "ns1.example.com.", "hostmaster.example.com.", 1, 3600, 900, 1_209_600, 300
    )
    assert parsed.targets == ()
    assert parsed.raw_names == ("NS1", "Hostmaster")
    assert (parsed.name_references[0].field, parsed.name_references[1].field) == ("mname", "rname")
    assert (parsed.name_references[0].line, parsed.name_references[1].line) == (9, 9)


@pytest.mark.parametrize(
    ("rtype", "tokens", "message"),
    [
        ("CNAME", (_token("*.y"),), 'invalid name "*.y"'),
        ("NS", (_token("*"),), 'invalid name "*"'),
        (
            "MX",
            (_token("10"), _token("*.y")),
            'invalid name "*.y"',
        ),
    ],
)
def test_wildcard_is_not_allowed_in_rdata_target_names(
    rtype: str, tokens: tuple[Token, ...], message: str
) -> None:
    with pytest.raises(ValueError) as error:
        parse_rdata(rtype, tokens, ORIGIN)

    assert str(error.value) == message


def test_txt_canonical_form_escapes_quotes_and_backslashes() -> None:
    value = 'say "hi"\\'
    parsed = parse_rdata("TXT", (_token(value, quoted=True),), ORIGIN)

    assert parsed.values == (value,)
    assert parsed.canonical == r'"say \"hi\"\\"'


def test_txt_accepts_handwritten_255_utf8_byte_string() -> None:
    assert len(_UTF8_255_BYTES.encode("utf-8")) == 255
    parsed = parse_rdata("TXT", (_token(_UTF8_255_BYTES, quoted=True),), ORIGIN)

    assert parsed.values == (_UTF8_255_BYTES,)
    assert parsed.canonical == f'"{_UTF8_255_BYTES}"'


def test_txt_rejects_handwritten_256_utf8_byte_string() -> None:
    assert len(_UTF8_128.encode("utf-8")) == 256
    with pytest.raises(ValueError) as error:
        parse_rdata("TXT", (_token(_UTF8_128, quoted=True),), ORIGIN)

    assert str(error.value) == "string longer than 255 bytes"


def test_txt_accepts_empty_individual_string() -> None:
    parsed = parse_rdata("TXT", (_token("", quoted=True),), ORIGIN)

    assert parsed.values == ("",)
    assert parsed.canonical == '""'


def test_soa_rejects_invalid_time_with_ttl_diagnostic() -> None:
    tokens = (
        _token("ns"), _token("hostmaster"), _token("1"), _token("not-a-ttl"),
        _token("1"), _token("1"), _token("1"),
    )

    with pytest.raises(ValueError) as error:
        parse_rdata("SOA", tokens, ORIGIN)

    assert str(error.value) == 'invalid TTL "not-a-ttl"'
