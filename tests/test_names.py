"""Examples for DNS name resolution, validation, and zone membership."""

import pytest

from zonevet.names import in_zone, resolve_name


@pytest.mark.parametrize(
    ("value", "origin", "allow_wildcard", "expected"),
    [
        ("@", "Example.COM.", False, "example.com."),
        (".", None, False, "."),
        ("www", "Example.COM.", False, "www.example.com."),
        ("WWW.Example.NET.", "example.com.", False, "www.example.net."),
        ("_sip._tcp", "example.com.", False, "_sip._tcp.example.com."),
        ("mail-host_1", "example.com.", False, "mail-host_1.example.com."),
        ("*.example", "example.com.", True, "*.example.example.com."),
        ("*", "example.com.", True, "*.example.com."),
    ],
)
def test_resolve_name_canonicalizes_valid_names(
    value: str, origin: str | None, allow_wildcard: bool, expected: str
) -> None:
    assert resolve_name(value, origin, allow_wildcard) == expected


@pytest.mark.parametrize(
    ("value", "origin", "allow_wildcard", "message"),
    [
        ("@", None, False, 'invalid name "@"'),
        ("www", None, False, 'invalid name "www"'),
        ("", "example.com.", False, 'invalid name ""'),
        ("a..b", "example.com.", False, 'invalid name "a..b"'),
        (".example", "example.com.", False, 'invalid name ".example"'),
        ("example..", "example.com.", False, 'invalid name "example.."'),
        ("bad/name", "example.com.", False, 'invalid name "bad/name"'),
        ("bad:name", "example.com.", False, 'invalid name "bad:name"'),
        ("münchen", "example.com.", False, 'invalid name "m?nchen"'),
        ("bad*label", "example.com.", True, 'invalid name "bad*label"'),
        ("a.*.example", "example.com.", True, 'invalid name "a.*.example"'),
        ("*.example", "example.com.", False, 'invalid name "*.example"'),
        ("*", "example.com.", False, 'invalid name "*"'),
    ],
)
def test_resolve_name_rejects_invalid_names(
    value: str, origin: str | None, allow_wildcard: bool, message: str
) -> None:
    with pytest.raises(ValueError) as caught:
        resolve_name(value, origin, allow_wildcard)

    assert str(caught.value) == message


def test_resolve_name_accepts_label_and_total_name_boundaries() -> None:
    label_63 = "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaa"
    label_61 = "bbbbbbbbbbbbbbbbbbbb" "bbbbbbbbbbbbbbbbbbbb" "bbbbbbbbbbbbbbbbbbbb" "b"
    assert len(label_63) == 63
    assert len(label_61) == 61
    assert resolve_name(label_63, ".", False) == f"{label_63}."
    boundary_name = (
        "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaa."
        "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaa."
        "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaa."
        "bbbbbbbbbbbbbbbbbbbb" "bbbbbbbbbbbbbbbbbbbb" "bbbbbbbbbbbbbbbbbbbb" "b."
    )
    assert len(boundary_name[:-1]) == 253
    assert resolve_name(boundary_name, None) == boundary_name.lower()


def test_resolve_name_rejects_labels_and_names_over_their_limits() -> None:
    label_64 = "cccccccccccccccccccc" "cccccccccccccccccccc" "cccccccccccccccccccc" "cccc"
    assert len(label_64) == 64
    with pytest.raises(ValueError) as caught_label:
        resolve_name(label_64, ".", False)
    assert str(caught_label.value) == f'invalid name "{label_64}"'

    overlong_name = (
        "dddddddddddddddddddd" "dddddddddddddddddddd" "dddddddddddddddddddd" "ddd."
        "dddddddddddddddddddd" "dddddddddddddddddddd" "dddddddddddddddddddd" "ddd."
        "dddddddddddddddddddd" "dddddddddddddddddddd" "dddddddddddddddddddd" "ddd."
        "dddddddddddddddddddd" "dddddddddddddddddddd" "dddddddddddddddddddd" "ddd."
    )
    assert len(overlong_name[:-1]) == 255
    with pytest.raises(ValueError) as caught_name:
        resolve_name(overlong_name, None)
    assert str(caught_name.value) == f'invalid name "{overlong_name}"'


def test_resolve_name_reports_original_relative_value_at_total_length_boundary() -> None:
    origin = (
        "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaa."
        "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaa."
        "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaaaaaaaaaaaaaaaaaaa" "aaa."
        "bbbbbbbbbbbbbbbbbbbb" "bbbbbbbbbbbbbbbbbbbb" "bbbbbbbbbbbbbbbbbbb."
    )

    boundary_name = resolve_name("x", origin)
    assert len(boundary_name[:-1]) == 253

    with pytest.raises(ValueError) as caught:
        resolve_name("xx", origin)
    assert str(caught.value) == 'invalid name "xx"'


@pytest.mark.parametrize(
    ("name", "apex", "expected"),
    [
        ("example.com.", "example.com.", True),
        ("EXAMPLE.COM.", "example.com.", True),
        ("www.example.com.", "example.com.", True),
        ("a.b.example.com.", "example.com.", True),
        ("notexample.com.", "example.com.", False),
        ("example.com.evil.", "example.com.", False),
        ("example.net.", "example.com.", False),
        (".", ".", True),
        ("www.example.com.", ".", True),
    ],
)
def test_in_zone_uses_apex_and_label_boundaries(name: str, apex: str, expected: bool) -> None:
    assert in_zone(name, apex) is expected
