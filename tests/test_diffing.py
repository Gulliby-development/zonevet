"""Example-based tests for structured zone differences."""

import pytest

from zonevet.diffing import diff_zones
from zonevet.zone import parse_zone

PREFIX = "$ORIGIN example.com.\n$TTL 300\n"


def _zone(records: str):
    return parse_zone(PREFIX + records)


def _diff(old: str, new: str):
    return diff_zones(_zone(old), _zone(new))


def test_additions_and_removals_are_sorted_by_owner_type_and_rdata() -> None:
    result = _diff(
        "z A 192.0.2.1\na A 192.0.2.1\na AAAA ::1\na A 192.0.2.2\n",
        "a A 192.0.2.1\na A 192.0.2.3\nb A 192.0.2.1\n",
    )

    assert [(change.kind, change.key) for change in result.changes] == [
        ("removed", ("a.example.com.", "A", "192.0.2.2")),
        ("added", ("a.example.com.", "A", "192.0.2.3")),
        ("removed", ("a.example.com.", "AAAA", "::1")),
        ("added", ("b.example.com.", "A", "192.0.2.1")),
        ("removed", ("z.example.com.", "A", "192.0.2.1")),
    ]


def test_rdata_keys_use_code_point_order() -> None:
    result = _diff(
        "host A 192.0.2.9\nhost A 192.0.2.2\nhost A 192.0.2.10\n",
        "",
    )

    assert [change.key[2] for change in result.changes] == [
        "192.0.2.10",
        "192.0.2.2",
        "192.0.2.9",
    ]


def test_ttl_only_change_retains_both_first_records() -> None:
    result = _diff("host 300 A 192.0.2.1\n", "host 600 A 192.0.2.1\n")

    assert len(result.changes) == 1
    change = result.changes[0]
    assert change.kind == "ttl"
    assert change.key == ("host.example.com.", "A", "192.0.2.1")
    assert change.old is not None and change.old.ttl == 300
    assert change.new is not None and change.new.ttl == 600
    assert result.record_change_count == 1
    assert result.has_changes


def test_first_duplicate_key_in_each_zone_supplies_the_ttl() -> None:
    result = _diff(
        "host 600 A 192.0.2.1\nhost 300 A 192.0.2.1\n",
        "host 900 A 192.0.2.1\nhost 200 A 192.0.2.1\n",
    )

    assert len(result.changes) == 1
    assert result.changes[0].kind == "ttl"
    assert result.changes[0].old is not None and result.changes[0].old.ttl == 600
    assert result.changes[0].new is not None and result.changes[0].new.ttl == 900


def test_soa_is_excluded_from_record_keys_and_first_soa_supplies_serial() -> None:
    result = _diff(
        "@ SOA ns host 1 600 60 2000 300\n@ SOA ns host 2 600 60 2000 300\n",
        "@ SOA ns host 3 600 60 2000 300\n@ SOA ns host 4 600 60 2000 300\n",
    )

    assert result.changes == ()
    assert result.record_change_count == 0
    assert result.serial_transition == (1, 3)
    assert result.warning_serial is None
    assert result.has_changes


def test_identical_zones_have_no_record_or_serial_difference() -> None:
    result = _diff(
        "@ SOA ns host 7 600 60 2000 300\nhost A 192.0.2.1\n",
        "@ SOA ns host 7 600 60 2000 300\nhost A 192.0.2.1\n",
    )

    assert result.changes == ()
    assert result.serial_transition is None
    assert result.warning_serial is None
    assert result.record_change_count == 0
    assert not result.has_changes


def test_empty_zones_are_identical() -> None:
    result = _diff("", "")

    assert result.changes == ()
    assert result.serial_transition is None
    assert result.warning_serial is None
    assert not result.has_changes


def test_missing_soa_omits_serial_comparison_and_warning() -> None:
    result = _diff(
        "@ SOA ns host 7 600 60 2000 300\nold A 192.0.2.1\n",
        "new A 192.0.2.1\n",
    )

    assert [(change.kind, change.key[0]) for change in result.changes] == [
        ("added", "new.example.com."),
        ("removed", "old.example.com."),
    ]
    assert result.serial_transition is None
    assert result.warning_serial is None
    assert result.record_change_count == 2
    assert result.has_changes


@pytest.mark.parametrize(
    ("old_serial", "new_serial", "expected_transition", "expected_warning", "expected_changes"),
    [
        (1, 2, (1, 2), None, True),
        (2, 2, None, None, False),
        (2, 1, (2, 1), None, True),
    ],
)
def test_serial_only_differences_are_separate_from_record_counts(
    old_serial: int,
    new_serial: int,
    expected_transition: tuple[int, int] | None,
    expected_warning: int | None,
    expected_changes: bool,
) -> None:
    result = _diff(
        f"@ SOA ns host {old_serial} 600 60 2000 300\n",
        f"@ SOA ns host {new_serial} 600 60 2000 300\n",
    )

    assert result.changes == ()
    assert result.record_change_count == 0
    assert result.serial_transition == expected_transition
    assert result.warning_serial == expected_warning
    assert result.has_changes is expected_changes


@pytest.mark.parametrize(
    ("old_serial", "new_serial", "expected_warning"),
    [
        (10, 11, None),
        (10, 10, 10),
        (10, 9, 9),
    ],
)
def test_record_changes_warn_when_serial_does_not_increase(
    old_serial: int, new_serial: int, expected_warning: int | None
) -> None:
    result = _diff(
        f"@ SOA ns host {old_serial} 600 60 2000 300\nold A 192.0.2.1\n",
        f"@ SOA ns host {new_serial} 600 60 2000 300\nnew A 192.0.2.1\n",
    )

    assert result.record_change_count == 2
    assert result.serial_transition == (
        (old_serial, new_serial) if old_serial != new_serial else None
    )
    assert result.warning_serial == expected_warning
    assert result.has_changes


def test_record_changes_without_both_serials_do_not_warn() -> None:
    result = _diff("old A 192.0.2.1\n", "new A 192.0.2.1\n")

    assert result.record_change_count == 2
    assert result.serial_transition is None
    assert result.warning_serial is None
    assert result.has_changes


def test_record_changes_alias_is_the_same_sorted_tuple() -> None:
    result = _diff("z A 192.0.2.1\na A 192.0.2.1\n", "")

    assert result.record_changes == result.changes
    assert [change.key[0] for change in result.record_changes] == [
        "a.example.com.",
        "z.example.com.",
    ]
