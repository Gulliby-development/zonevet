"""Example-based regression coverage for IPv4-shaped DNS targets."""

import io
from dataclasses import replace
from pathlib import Path

import pytest

from zonevet.checks import check_zone
from zonevet.cli import main
from zonevet.zone import parse_zone

PREFIX = "$ORIGIN example.com.\n$TTL 300\n"


def _findings(source: str) -> tuple[tuple[int, str, str], ...]:
    zone = parse_zone(PREFIX + source)
    return tuple((finding.line, finding.code, finding.message) for finding in check_zone(zone))


def _for_code(source: str, code: str) -> tuple[tuple[int, str, str], ...]:
    return tuple(finding for finding in _findings(source) if finding[1] == code)


@pytest.mark.parametrize(
    ("rtype", "rdata", "target"),
    [
        ("CNAME", "192.0.2.53", "192.0.2.53"),
        ("CNAME", "192.0.2.53.", "192.0.2.53."),
        ("NS", "192.0.2.53", "192.0.2.53"),
        ("NS", "192.0.2.53.", "192.0.2.53."),
        ("MX", "10 192.0.2.53", "192.0.2.53"),
        ("MX", "10 192.0.2.53.", "192.0.2.53."),
        ("SRV", "0 1 2 192.0.2.53", "192.0.2.53"),
        ("SRV", "0 1 2 192.0.2.53.", "192.0.2.53."),
    ],
)
def test_supported_targets_flag_relative_and_absolute_addresses(
    rtype: str, rdata: str, target: str
) -> None:
    assert _for_code(f"@ {rtype} {rdata}\n", "ZC112") == (
        (3, "ZC112", f'{rtype} target "{target}" looks like an IPv4 address (use a host name)'),
    )


@pytest.mark.parametrize(
    "target",
    [
        "1.2.3.4",
        "0.0.0.0",
        "999.999.999.999",
    ],
)
def test_address_shape_does_not_validate_octet_ranges(target: str) -> None:
    assert _for_code(f"@ NS {target}\n", "ZC112") == (
        (3, "ZC112", f'NS target "{target}" looks like an IPv4 address (use a host name)'),
    )


@pytest.mark.parametrize(
    "target",
    [
        "1.2.3",
        "1.2.3.4.5",
        "1234.2.3.4",
        "1.2.3.4x",
        "a.b.c.d",
        "host1.2.3.4",
        "192.0.2.1.example.com.",
    ],
)
def test_non_address_target_shapes_are_not_flagged(target: str) -> None:
    assert _for_code(f"@ NS {target}\n", "ZC112") == ()


def test_non_ascii_digits_are_not_ipv4_target() -> None:
    zone = parse_zone(PREFIX + "@ NS 1.2.3.4\n")
    record = zone.records[0]
    target_reference = replace(record.rdata.name_references[0], raw="١.٢.٣.٤")
    record = replace(
        record,
        rdata=replace(record.rdata, name_references=(target_reference,)),
        name_references=(record.name_references[0], target_reference),
    )
    zone = replace(zone, records=(record,))

    assert tuple(finding.code for finding in check_zone(zone) if finding.code == "ZC112") == ()


def test_owners_and_non_target_fields_or_types_are_not_flagged() -> None:
    source = (
        "192.0.2.53 CNAME canonical\n"
        "192.0.2.54 NS nameserver\n"
        "192.0.2.55 MX 10 mail\n"
        "192.0.2.56 SRV 0 1 2 service\n"
        "192.0.2.57 A 192.0.2.58\n"
        "192.0.2.59 AAAA 2001:db8::1\n"
        '192.0.2.60 TXT "192.0.2.61"\n'
        "192.0.2.62 PTR 192.0.2.63\n"
        "@ SOA ns host 1 600 60 2000 300\n"
    )
    assert _for_code(source, "ZC112") == ()


def test_multiple_targets_are_reported_in_source_order() -> None:
    source = (
        "@ NS 192.0.2.53\n"
        "@ MX 10 192.0.2.25\n"
        "_sip._tcp SRV 0 1 2 192.0.2.80\n"
        "alias CNAME 192.0.2.99.\n"
    )
    assert _for_code(source, "ZC112") == (
        (3, "ZC112", 'NS target "192.0.2.53" looks like an IPv4 address (use a host name)'),
        (4, "ZC112", 'MX target "192.0.2.25" looks like an IPv4 address (use a host name)'),
        (5, "ZC112", 'SRV target "192.0.2.80" looks like an IPv4 address (use a host name)'),
        (6, "ZC112", 'CNAME target "192.0.2.99." looks like an IPv4 address (use a host name)'),
    )


def test_parenthesized_target_uses_the_target_line() -> None:
    source = "@ MX (\n  10\n  192.0.2.25 )\n"
    assert _for_code(source, "ZC112") == (
        (5, "ZC112", 'MX target "192.0.2.25" looks like an IPv4 address (use a host name)'),
    )


def test_existing_same_line_findings_sort_before_zc112() -> None:
    assert _findings("@ NS 192.0.2.53\n") == (
        (1, "ZC101", "missing SOA record"),
        (3, "ZC106", 'NS target "192.0.2.53.example.com." has no A or AAAA record'),
        (3, "ZC112", 'NS target "192.0.2.53" looks like an IPv4 address (use a host name)'),
    )
    assert _findings("www.example.com CNAME 192.0.2.53\n") == (
        (1, "ZC101", "missing SOA record"),
        (3, "ZC109", "no NS record at the zone apex"),
        (
            3,
            "ZC111",
            '"www.example.com" is relative and ends with the zone name (missing trailing dot?)',
        ),
        (3, "ZC112", 'CNAME target "192.0.2.53" looks like an IPv4 address (use a host name)'),
    )


def test_cli_worked_example_has_exact_output_and_exit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    Path("addr.zone").write_bytes(
        b"$ORIGIN example.com.\n"
        b"$TTL 1h\n"
        b"@       IN SOA ns1 hostmaster 2024010101 2h 15m 2w 1h\n"
        b"        IN NS   ns1\n"
        b"        IN MX   10 192.0.2.25\n"
        b"ns1     IN A    192.0.2.53\n"
        b"www     IN CNAME 192.0.2.80.\n"
    )
    stdout, stderr = io.StringIO(), io.StringIO()

    status = main(["check", "addr.zone"], stdin=io.BytesIO(), stdout=stdout, stderr=stderr)

    assert (status, stdout.getvalue(), stderr.getvalue()) == (
        1,
        (
            'addr.zone:5: ZC106 MX target "192.0.2.25.example.com." has no A or AAAA record\n'
            'addr.zone:5: ZC112 MX target "192.0.2.25" looks like an IPv4 address (use a host name)\n'
            'addr.zone:7: ZC112 CNAME target "192.0.2.80." looks like an IPv4 address (use a host name)\n'
            "3 problems in 1 file, 1 file checked\n"
        ),
        "",
    )
