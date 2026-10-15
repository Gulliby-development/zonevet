"""Example-based coverage for semantic zone findings."""

import pytest

from zonevet.checks import check_zone
from zonevet.zone import parse_zone

PREFIX = "$ORIGIN example.com.\n$TTL 300\n"


def _findings(source: str) -> tuple[tuple[int, str, str], ...]:
    zone = parse_zone(PREFIX + source)
    return tuple((finding.line, finding.code, finding.message) for finding in check_zone(zone))


def _for_code(source: str, code: str) -> tuple[tuple[int, str, str], ...]:
    return tuple(finding for finding in _findings(source) if finding[1] == code)


def test_empty_zone_reports_only_missing_soa_at_line_one() -> None:
    assert _findings("") == ((1, "ZC101", "missing SOA record"),)


def test_nonempty_zone_without_soa_reports_missing_soa() -> None:
    assert _findings("@ NS ns\nns A 192.0.2.1\n") == (
        (1, "ZC101", "missing SOA record"),
    )


def test_soa_position_and_each_additional_soa() -> None:
    source = (
        "host A 192.0.2.1\n"
        "@ SOA ns host 1 600 60 2000 300\n"
        "@ SOA ns host 2 600 60 2000 300\n"
        "@ SOA ns host 3 600 60 2000 300\n"
    )
    assert _for_code(source, "ZC101") == (
        (4, "ZC101", "SOA is not the first record"),
        (5, "ZC101", "more than one SOA record"),
        (6, "ZC101", "more than one SOA record"),
    )


def test_duplicate_ignores_ttl_but_compares_canonical_rdata() -> None:
    source = (
        "host 600 A 192.0.2.1\n"
        "host 300 A 192.0.2.1\n"
        "host 300 A 192.0.2.2\n"
    )
    assert _for_code(source, "ZC102") == ((4, "ZC102", "duplicate of line 3"),)


def test_cname_coexistence_and_second_cname_use_first_occurrences() -> None:
    source = (
        "www A 192.0.2.1\n"
        "www CNAME target\n"
        "www CNAME other\n"
        "www CNAME third\n"
    )
    assert _for_code(source, "ZC103") == (
        (4, "ZC103", '"www.example.com." has a CNAME and other data (line 3)'),
        (5, "ZC103", 'second CNAME at "www.example.com."'),
    )


def test_single_cname_without_other_data_is_not_a_conflict() -> None:
    assert _for_code("alias CNAME target\n", "ZC103") == ()


@pytest.mark.parametrize(
    ("rtype", "rdata"),
    [
        ("NS", "www"),
        ("MX", "10 www"),
        ("SRV", "0 1 2 www"),
    ],
)
def test_ns_mx_and_srv_targets_that_are_cnames_are_reported(rtype: str, rdata: str) -> None:
    source = f"www CNAME target\n@ {rtype} {rdata}\n"
    assert _for_code(source, "ZC104") == (
        (4, "ZC104", f'{rtype} target "www.example.com." is a CNAME (line 3)'),
    )


def test_root_alias_target_is_excluded() -> None:
    assert _for_code("alias CNAME target\n@ NS .\n", "ZC104") == ()


def test_cname_self_loop_is_reported_once() -> None:
    assert _for_code("a CNAME a\n", "ZC105") == (
        (3, "ZC105", "CNAME loop: a.example.com. -> a.example.com."),
    )


def test_each_cname_cycle_is_reported_from_its_smallest_line() -> None:
    source = (
        "a CNAME b\n"
        "b CNAME a\n"
        "bridge CNAME a\n"
        "x CNAME y\n"
        "y CNAME x\n"
    )
    assert _for_code(source, "ZC105") == (
        (3, "ZC105", "CNAME loop: a.example.com. -> b.example.com. -> a.example.com."),
        (6, "ZC105", "CNAME loop: x.example.com. -> y.example.com. -> x.example.com."),
    )


@pytest.mark.parametrize(
    ("rtype", "rdata"),
    [
        ("NS", "missing"),
        ("MX", "10 missing"),
        ("SRV", "0 1 2 missing"),
    ],
)
def test_in_zone_non_cname_targets_without_address_are_reported(
    rtype: str, rdata: str
) -> None:
    owner = "_" + "service._tcp" if rtype == "SRV" else "@"
    assert _for_code(f"{owner} {rtype} {rdata}\n", "ZC106") == (
        (3, "ZC106", f'{rtype} target "missing.example.com." has no A or AAAA record'),
    )


def test_root_external_cname_and_addressed_targets_are_excluded_but_wildcard_is_not_address() -> None:
    source = (
        "@ NS outside.example.net.\n"
        "@ NS .\n"
        "@ NS alias\n"
        "alias CNAME nowhere\n"
        "@ NS ipv4\n"
        "ipv4 A 192.0.2.1\n"
        "@ NS ipv6\n"
        "ipv6 AAAA ::1\n"
        "@ NS host\n"
        "*.example.com A 192.0.2.9\n"
    )
    assert _for_code(source, "ZC106") == (
        (11, "ZC106", 'NS target "host.example.com." has no A or AAAA record'),
    )


def test_rrset_reports_first_later_ttl_that_differs_only_once() -> None:
    source = (
        "ns 600 A 192.0.2.1\n"
        "ns 600 A 192.0.2.2\n"
        "ns 300 A 192.0.2.3\n"
        "ns 200 A 192.0.2.4\n"
        "ns 900 AAAA ::1\n"
        "ns 900 AAAA ::2\n"
    )
    assert _for_code(source, "ZC107") == (
        (
            5,
            "ZC107",
            'RRset "ns.example.com." A has different TTLs (600 on line 3, 300 on line 5)',
        ),
    )


def test_rrset_with_consistent_ttls_has_no_finding() -> None:
    assert _for_code("ns 600 A 192.0.2.1\nns 600 A 192.0.2.2\n", "ZC107") == ()


def test_owner_outside_apex_is_reported() -> None:
    assert _for_code("other.org. A 192.0.2.1\n", "ZC108") == (
        (3, "ZC108", '"other.org." is outside the zone "example.com."'),
    )


def test_subdomain_ns_does_not_satisfy_apex_ns() -> None:
    assert _for_code("sub NS ns\nns A 192.0.2.1\n", "ZC109") == (
        (3, "ZC109", "no NS record at the zone apex"),
    )


def _soa_source(refresh: int, retry: int, expire: int) -> str:
    return (
        f"@ SOA ns host 1 {refresh} {retry} {expire} 300\n"
        "@ NS ns\n"
        "ns A 192.0.2.1\n"
    )


@pytest.mark.parametrize(
    ("refresh", "retry", "expire", "expected"),
    [
        (600, 600, 2000, ((3, "ZC110", "SOA retry (600) is not smaller than refresh (600)"),)),
        (600, 700, 2000, ((3, "ZC110", "SOA retry (700) is not smaller than refresh (600)"),)),
        (
            600,
            60,
            660,
            ((3, "ZC110", "SOA expire (660) is not larger than refresh plus retry (660)"),),
        ),
        (
            600,
            60,
            659,
            ((3, "ZC110", "SOA expire (659) is not larger than refresh plus retry (660)"),),
        ),
        (600, 60, 661, ()),
    ],
)
def test_soa_retry_and_expire_thresholds(
    refresh: int, retry: int, expire: int, expected: tuple[tuple[int, str, str], ...]
) -> None:
    assert _for_code(_soa_source(refresh, retry, expire), "ZC110") == expected


@pytest.mark.parametrize(
    ("label", "record"),
    [
        ("explicit owner", "www.example.com A 192.0.2.1"),
        ("SOA MNAME", "@ SOA ns.example.com hostmaster 1 600 60 2000 300"),
        ("CNAME target", "alias CNAME ns.example.com"),
        ("NS target", "@ NS ns.example.com"),
        ("PTR target", "ptr PTR ns.example.com"),
        ("MX target", "@ MX 10 ns.example.com"),
        ("SRV target", "_sip._tcp SRV 1 2 3 ns.example.com"),
    ],
)
def test_relative_names_ending_in_zone_name_are_flagged(label: str, record: str) -> None:
    del label
    assert _for_code(record + "\n", "ZC111") == (
        (3, "ZC111", '"ns.example.com" is relative and ends with the zone name (missing trailing dot?)')
        if record.startswith("@ SOA")
        else (
            3,
            "ZC111",
            (
                '"www.example.com" is relative and ends with the zone name (missing trailing dot?)'
                if record.startswith("www.")
                else '"ns.example.com" is relative and ends with the zone name (missing trailing dot?)'
            ),
        ),
    )


def test_trailing_dot_checks_preserve_same_line_reference_order() -> None:
    source = "www.example.com CNAME api.example.com\n"
    assert _for_code(source, "ZC111") == (
        (3, "ZC111", '"www.example.com" is relative and ends with the zone name (missing trailing dot?)'),
        (3, "ZC111", '"api.example.com" is relative and ends with the zone name (missing trailing dot?)'),
    )


def test_at_inherited_absolute_and_nonmatching_label_boundary_are_excluded() -> None:
    source = (
        "@ NS ns\n"
        "    A 192.0.2.1\n"
        "notexample.com A 192.0.2.2\n"
        "@ NS ns.example.com.\n"
    )
    assert _for_code(source, "ZC111") == ()


def test_first_soa_does_not_trigger_soa_position_findings() -> None:
    assert _for_code("@ SOA ns host 1 600 60 2000 300\n", "ZC101") == ()


def test_distinct_rdata_and_types_are_not_duplicates() -> None:
    source = "host A 192.0.2.1\nhost A 192.0.2.2\nhost AAAA ::1\n"
    assert _for_code(source, "ZC102") == ()


def test_acyclic_cname_chain_has_no_loop() -> None:
    assert _for_code("a CNAME b\nb A 192.0.2.1\n", "ZC105") == ()


def test_owner_inside_apex_is_not_outside() -> None:
    assert _for_code("www A 192.0.2.1\n", "ZC108") == ()


def test_apex_ns_suppresses_missing_apex_ns() -> None:
    assert _for_code("@ NS ns\nns A 192.0.2.1\n", "ZC109") == ()
