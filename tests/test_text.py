import pytest

from zonevet.text import display, plural, quote


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", '""'),
        ("plain", '"plain"'),
        ("!~.,/:;?@[]{}", '"!~.,/:;?@[]{}"'),
        ("a b", '"a?b"'),
        (" \t\n", '"???"'),
        ("\x00é🙂", '"???"'),
        ('a"b', '"a"b"'),
    ],
)
def test_quote_replaces_each_non_printable_code_point(value: str, expected: str) -> None:
    assert quote(value) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("folder\\zone.zone", "folder/zone.zone"),
        ("folder/sub\\nested\\zone.zone", "folder/sub/nested/zone.zone"),
        ("/tmp/zone.zone", "/tmp/zone.zone"),
        ("", ""),
    ],
)
def test_display_normalizes_path_separators(path: str, expected: str) -> None:
    assert display(path) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "files"),
        (1, "file"),
        (2, "files"),
    ],
)
def test_plural_uses_default_plural_form(count: int, expected: str) -> None:
    assert plural(count, "file") == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "problems"),
        (1, "problem"),
        (2, "problems"),
    ],
)
def test_plural_uses_explicit_plural_form(count: int, expected: str) -> None:
    assert plural(count, "problem", "problems") == expected
