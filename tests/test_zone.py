"""Examples for zone parsing, source metadata and syntax-error precedence."""

import pytest

from zonevet.zone import ZoneError, parse_zone

SYNTAX_ERRORS = [
    ("$TTL\n", None, 1, 'expected "$TTL TTL"'),
    ("$TTL 60 extra\n", None, 1, 'expected "$TTL TTL"'),
    ('$TTL "60"\n', None, 1, 'expected "$TTL TTL"'),
    ("$TTL 1x\n", None, 1, 'invalid TTL "1x"'),
    ("$ORIGIN\n", None, 1, 'expected "$ORIGIN NAME"'),
    ("$ORIGIN x. y.\n", None, 1, 'expected "$ORIGIN NAME"'),
    ("$ORIGIN sub\n", None, 1, 'invalid $ORIGIN "sub" (expected an absolute name such as example.com.)'),
    ("$ORIGIN bad..org.\n", None, 1, 'invalid name "bad..org."'),
    ("$INCLUDE file\n", None, 1, 'unknown directive "$INCLUDE"'),
    ("  IN A 192.0.2.1\n", "example.com.", 1, "no previous owner"),
    ('"x" A 192.0.2.1\n', "example.com.", 1, "expected an owner name"),
    ("$ORIGIN example.com.\n$TTL 60\nx\n", None, 3, "missing record type"),
    ("$ORIGIN example.com.\n$TTL 60\nx IN\n", None, 3, "missing record type"),
    ("$ORIGIN example.com.\n$TTL 60\nx CS A 192.0.2.1\n", None, 3, 'unsupported class "CS"'),
    ("$ORIGIN example.com.\n$TTL 60\nx CH A 192.0.2.1\n", None, 3, 'unsupported class "CH"'),
    ("$ORIGIN example.com.\n$TTL 60\nx HS A 192.0.2.1\n", None, 3, 'unsupported class "HS"'),
    ("$ORIGIN example.com.\n$TTL 60\nx 60 IN HINFO value\n", None, 3, 'unknown record type "HINFO"'),
    ("x A 192.0.2.1\n", None, 1, "no origin (add $ORIGIN or use --origin)"),
    ("$ORIGIN example.com.\nx A 192.0.2.1\n", None, 2, "no TTL (add $TTL or give one)"),
    ("$ORIGIN example.com.\n$TTL 60\nx 1x A 192.0.2.1\n", None, 3, 'invalid TTL "1x"'),
    ("$ORIGIN example.com.\n$TTL 60\na..b A 192.0.2.1\n", None, 3, 'invalid name "a..b"'),
    ("$ORIGIN example.com.\n$TTL 60\na/b A 192.0.2.1\n", None, 3, 'invalid name "a/b"'),
    ("$ORIGIN example.com.\n$TTL 60\nx A\n", None, 3, 'expected "A ADDRESS"'),
    ("$ORIGIN example.com.\n$TTL 60\nx A 192.0.2.01\n", None, 3, 'invalid IPv4 address "192.0.2.01"'),
    ("$ORIGIN example.com.\n$TTL 60\nx CNAME\n", None, 3, 'expected "CNAME NAME"'),
    ("$ORIGIN example.com.\n$TTL 60\nx CNAME *.y\n", None, 3, 'invalid name "*.y"'),
    ("$ORIGIN example.com.\n$TTL 60\nx CNAME target extra\n", None, 3, 'expected "CNAME NAME"'),
    ("$ORIGIN example.com.\n$TTL 60\nx IN IN A 192.0.2.1\n", None, 3, 'unknown record type "IN"'),
]


@pytest.mark.parametrize(("source", "origin", "line", "message"), SYNTAX_ERRORS)
def test_syntax_errors_have_exact_line_and_message(
    source: str, origin: str | None, line: int, message: str
) -> None:
    with pytest.raises(ZoneError) as caught:
        parse_zone(source, origin=origin)

    assert caught.value.line == line
    assert caught.value.message == message
    assert str(caught.value) == message


def test_empty_and_directive_only_zones_have_no_records_or_apex() -> None:
    assert parse_zone("").records == ()
    zone = parse_zone("$ORIGIN example.com.\n$TTL 300\n")
    assert zone.records == ()
    assert zone.apex is None


def test_records_keep_canonical_values_source_names_and_initial_apex() -> None:
    source = (
        "\ufeff$ORIGIN Example.COM.\r\n"
        "$TTL 1h\r\n"
        "@ IN SOA ns hostmaster (\r\n"
        "  2024010101 2h 15m 2w 1h )\r\n"
        "  IN NS ns1\r\n"
        "$ORIGIN Sub.Example.com.\r\n"
        "mail 300 IN A 192.0.2.25\r\n"
    )

    zone = parse_zone(source)

    assert zone.apex == "example.com."
    assert [record.line for record in zone.records] == [3, 5, 7]
    assert [record.canonical for record in zone.records] == [
        (
            "example.com. 3600 IN SOA ns.example.com. hostmaster.example.com. "
            "2024010101 7200 900 1209600 3600"
        ),
        "example.com. 3600 IN NS ns1.example.com.",
        "mail.sub.example.com. 300 IN A 192.0.2.25",
    ]
    assert zone.records[0].raw_names == ("@", "ns", "hostmaster")
    assert zone.records[1].raw_owner is None
    assert zone.records[1].owner_inherited is True
    assert zone.records[1].raw_names == ("ns1",)
    assert zone.records[2].raw_owner == "mail"
    assert zone.records[2].owner_inherited is False
    assert zone.records[2].raw_names == ("mail",)


def test_supported_record_types_render_canonically() -> None:
    source = (
        "$ORIGIN example.com.\n"
        "$TTL 60\n"
        "@ SOA ns hostmaster 1 2h 15m 2w 1h\n"
        "@ NS ns1\n"
        "@ MX 10 mail\n"
        "@ TXT \"one\" \"two\"\n"
        "www 300 IN CNAME web\n"
        "v6 IN AAAA 2001:0db8:0:0:0:0:0:1\n"
        "_sip._tcp SRV 10 60 5060 mail\n"
        "ptr PTR www\n"
        "www A 192.0.2.1\n"
    )

    zone = parse_zone(source)

    assert [record.canonical for record in zone.records] == [
        "example.com. 60 IN SOA ns.example.com. hostmaster.example.com. 1 7200 900 1209600 3600",
        "example.com. 60 IN NS ns1.example.com.",
        "example.com. 60 IN MX 10 mail.example.com.",
        'example.com. 60 IN TXT "one" "two"',
        "www.example.com. 300 IN CNAME web.example.com.",
        "v6.example.com. 60 IN AAAA 2001:db8::1",
        "_sip._tcp.example.com. 60 IN SRV 10 60 5060 mail.example.com.",
        "ptr.example.com. 60 IN PTR www.example.com.",
        "www.example.com. 60 IN A 192.0.2.1",
    ]


def test_earlier_invalid_entry_wins_over_later_lexical_error() -> None:
    source = "$ORIGIN example.com.\n$TTL 60\nx A\nnext )\n"

    with pytest.raises(ZoneError) as caught:
        parse_zone(source)

    assert caught.value.line == 3
    assert caught.value.message == 'expected "A ADDRESS"'
