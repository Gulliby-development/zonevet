"""Exact-output examples for report rendering."""

import pytest

from zonevet.checks import Finding
from zonevet.diffing import diff_zones
from zonevet.report import format_check, format_diff, format_list, format_usage
from zonevet.zone import parse_zone

USAGE = (
    "usage: zonevet check [--origin NAME] ZONE...\n"
    "       zonevet list [--origin NAME] [--type TYPE] ZONE\n"
    "       zonevet diff [--origin NAME] OLD NEW"
)


def test_format_usage_appends_exactly_one_lf() -> None:
    assert format_usage(USAGE) == USAGE + "\n"
    assert format_usage("") == "\n"


@pytest.mark.parametrize(
    ("results", "files_checked", "expected"),
    [
        (
            (("folder\\bad.zone", (Finding(3, "ZC001", 'invalid name "?"'),)),),
            1,
            (
                'folder/bad.zone:3: ZC001 invalid name "?"\n'
                "1 problem in 1 file, 1 file checked\n"
            ),
        ),
        (
            (
                (
                    "first.zone",
                    (
                        Finding(2, "ZC101", "missing SOA record"),
                        Finding(4, "ZC109", "no NS record at the zone apex"),
                    ),
                ),
                ("second.zone", (Finding(8, "ZC102", "duplicate of line 7"),)),
            ),
            3,
            (
                "first.zone:2: ZC101 missing SOA record\n"
                "first.zone:4: ZC109 no NS record at the zone apex\n"
                "second.zone:8: ZC102 duplicate of line 7\n"
                "3 problems in 2 files, 3 files checked\n"
            ),
        ),
        ((), 0, "ok, 0 files checked\n"),
        ((("empty.zone", ()),), 1, "ok, 1 file checked\n"),
        ((("one.zone", ()), ("two.zone", ())), 2, "ok, 2 files checked\n"),
    ],
)
def test_format_check_renders_findings_totals_paths_and_lf(
    results: tuple[tuple[str, tuple[Finding, ...]], ...], files_checked: int, expected: str
) -> None:
    assert format_check(results, files_checked) == expected


def test_format_list_preserves_canonical_source_order() -> None:
    zone = parse_zone(
        '$ORIGIN example.com.\n'
        '$TTL 60\n'
        '@ SOA ns host 1 600 60 2000 300\n'
        '@ NS ns\n'
        'ns A 192.0.2.1\n'
        'www AAAA ::1\n'
        '@ TXT "a" "b"\n'
    )
    assert format_list(zone) == (
        "example.com. 60 IN SOA ns.example.com. host.example.com. 1 600 60 2000 300\n"
        "example.com. 60 IN NS ns.example.com.\n"
        "ns.example.com. 60 IN A 192.0.2.1\n"
        "www.example.com. 60 IN AAAA ::1\n"
        'example.com. 60 IN TXT "a" "b"\n'
    )


@pytest.mark.parametrize(
    ("record_type", "expected"),
    [
        (
            "A",
            "ns.example.com. 60 IN A 192.0.2.1\n",
        ),
        (
            "AAAA",
            "www.example.com. 60 IN AAAA ::1\n",
        ),
        (
            "TXT",
            'example.com. 60 IN TXT "a" "b"\n',
        ),
        ("MX", ""),
    ],
)
def test_format_list_filters_by_type_and_empty_filter_is_empty(
    record_type: str, expected: str
) -> None:
    zone = parse_zone(
        '$ORIGIN example.com.\n'
        '$TTL 60\n'
        '@ SOA ns host 1 600 60 2000 300\n'
        'ns A 192.0.2.1\n'
        'www AAAA ::1\n'
        '@ TXT "a" "b"\n'
    )
    assert format_list(zone, record_type) == expected


def test_format_list_of_empty_zone_has_no_output() -> None:
    assert format_list(parse_zone("")) == ""


def test_format_diff_orders_markers_then_serial_summary_and_warning() -> None:
    old_zone = parse_zone(
        '$ORIGIN example.com.\n'
        '$TTL 300\n'
        '@ SOA ns host 2 600 60 2000 300\n'
        'z A 192.0.2.1\n'
        'ttl A 192.0.2.9\n'
        'gone AAAA ::1\n'
    )
    new_zone = parse_zone(
        '$ORIGIN example.com.\n'
        '$TTL 300\n'
        '@ SOA ns host 1 600 60 2000 300\n'
        'z A 192.0.2.2\n'
        'ttl 600 A 192.0.2.9\n'
        'added A 192.0.2.3\n'
    )
    assert format_diff(diff_zones(old_zone, new_zone)) == (
        "+ added.example.com. 300 IN A 192.0.2.3\n"
        "- gone.example.com. 300 IN AAAA ::1\n"
        "~ ttl.example.com. A 192.0.2.9: ttl 300 -> 600\n"
        "- z.example.com. 300 IN A 192.0.2.1\n"
        "+ z.example.com. 300 IN A 192.0.2.2\n"
        "serial 2 -> 1\n"
        "5 changes\n"
        "warning: the SOA serial did not increase (1)\n"
    )


def test_format_diff_singular_ttl_change_and_lf() -> None:
    old_zone = parse_zone(
        '$ORIGIN example.com.\n$TTL 60\n'
        '@ SOA ns host 1 600 60 2000 300\n'
        'www 300 A 192.0.2.1\n'
    )
    new_zone = parse_zone(
        '$ORIGIN example.com.\n$TTL 60\n'
        '@ SOA ns host 2 600 60 2000 300\n'
        'www 600 A 192.0.2.1\n'
    )
    assert format_diff(diff_zones(old_zone, new_zone)) == (
        "~ www.example.com. A 192.0.2.1: ttl 300 -> 600\n"
        "serial 1 -> 2\n"
        "1 change\n"
    )


def test_format_diff_serial_only_has_no_record_change_count_or_warning() -> None:
    old_zone = parse_zone(
        '$ORIGIN example.com.\n$TTL 60\n@ SOA ns host 1 600 60 2000 300\n'
    )
    new_zone = parse_zone(
        '$ORIGIN example.com.\n$TTL 60\n@ SOA ns host 2 600 60 2000 300\n'
    )
    assert format_diff(diff_zones(old_zone, new_zone)) == "serial 1 -> 2\nno changes\n"


def test_format_diff_identical_zones_reports_no_changes() -> None:
    zone = parse_zone(
        '$ORIGIN example.com.\n$TTL 60\n'
        '@ SOA ns host 1 600 60 2000 300\n'
        '@ NS ns\n'
    )
    assert format_diff(diff_zones(zone, zone)) == "no changes\n"
