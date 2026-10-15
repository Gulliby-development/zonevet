"""Argument grammar, diagnostics, and precedence examples."""

import pytest

from zonevet.args import USAGE, ParsedArgs, UsageError, parse_args


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--help"], ParsedArgs("help", None, None, ())),
        (["check", "zone"], ParsedArgs("check", None, None, ("zone",))),
        (
            ["check", "one", "-", "three"],
            ParsedArgs("check", None, None, ("one", "-", "three")),
        ),
        (
            ["check", "--origin", "EXAMPLE.COM.", "zone"],
            ParsedArgs("check", "example.com.", None, ("zone",)),
        ),
        (
            ["check", "zone", "--origin=EXAMPLE.COM."],
            ParsedArgs("check", "example.com.", None, ("zone",)),
        ),
        (
            ["check", "--origin", "bad", "--origin=EXAMPLE.COM.", "zone"],
            ParsedArgs("check", "example.com.", None, ("zone",)),
        ),
        (
            ["list", "zone", "--type", "a"],
            ParsedArgs("list", None, "A", ("zone",)),
        ),
        (
            ["list", "--type=aaaa", "zone"],
            ParsedArgs("list", None, "AAAA", ("zone",)),
        ),
        (
            ["list", "--type=HINFO", "--type=mx", "zone"],
            ParsedArgs("list", None, "MX", ("zone",)),
        ),
        (
            ["list", "--origin", "Example.COM.", "--type", "Txt", "zone"],
            ParsedArgs("list", "example.com.", "TXT", ("zone",)),
        ),
        (
            ["diff", "--origin=EXAMPLE.COM.", "old", "new"],
            ParsedArgs("diff", "example.com.", None, ("old", "new")),
        ),
        (
            ["diff", "old", "--origin", "example.com.", "new"],
            ParsedArgs("diff", "example.com.", None, ("old", "new")),
        ),
    ],
)
def test_parse_args_accepts_commands_options_and_operands(
    argv: list[str], expected: ParsedArgs
) -> None:
    assert parse_args(argv) == expected


def test_help_usage_has_the_three_prescribed_lines() -> None:
    assert USAGE == (
        "usage: zonevet check [--origin NAME] ZONE...\n"
        "       zonevet list [--origin NAME] [--type TYPE] ZONE\n"
        "       zonevet diff [--origin NAME] OLD NEW"
    )
    assert parse_args(["--help"]).command == "help"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "missing command (check, list or diff)"),
        (["inspect"], 'unknown command "inspect"'),
        (["dÉf"], 'unknown command "d?f"'),
        (["check", "--help"], 'unknown option "--help"'),
        (["list", "--help"], 'unknown option "--help"'),
        (["diff", "--help"], 'unknown option "--help"'),
        (["check", "--strange"], 'unknown option "--strange"'),
        (
            ["check", "--strange", "--origin", "bad", "--type", "HINFO"],
            'unknown option "--strange"',
        ),
        (["check", "--origin"], "--origin needs a value"),
        (["list", "--type"], "--type needs a value"),
        (["check", "--origin", "sub"], 'invalid --origin "sub" (expected an absolute name such as example.com.)'),
        (
            ["list", "--origin", "K.org.", "zone"],
            'invalid --origin "k.org." (expected an absolute name such as example.com.)',
        ),
        (
            ["list", "--origin=K.org.", "zone"],
            'invalid --origin "k.org." (expected an absolute name such as example.com.)',
        ),
        (["check", "--origin="], 'invalid --origin "" (expected an absolute name such as example.com.)'),
        (["check", "--origin", "-"], 'invalid --origin "-" (expected an absolute name such as example.com.)'),
        (
            ["check", "--origin", "--unknown"],
            'invalid --origin "--unknown" (expected an absolute name such as example.com.)',
        ),
        (
            ["list", "--type=HINFO"],
            'invalid --type "HINFO" (expected A, AAAA, CNAME, MX, NS, PTR, SOA, SRV or TXT)',
        ),
        (
            ["list", "--type=ſoa", "zone"],
            'invalid --type "?oa" (expected A, AAAA, CNAME, MX, NS, PTR, SOA, SRV or TXT)',
        ),
        (
            ["list", "--type="],
            'invalid --type "" (expected A, AAAA, CNAME, MX, NS, PTR, SOA, SRV or TXT)',
        ),
        (
            ["list", "--type", "--unknown"],
            'invalid --type "--unknown" (expected A, AAAA, CNAME, MX, NS, PTR, SOA, SRV or TXT)',
        ),
        (
            ["check", "--type=HINFO", "--origin=sub"],
            'invalid --origin "sub" (expected an absolute name such as example.com.)',
        ),
        (
            ["list", "--type=HINFO", "--origin=sub"],
            'invalid --origin "sub" (expected an absolute name such as example.com.)',
        ),
        (
            ["check", "--type=HINFO"],
            'invalid --type "HINFO" (expected A, AAAA, CNAME, MX, NS, PTR, SOA, SRV or TXT)',
        ),
        (["check", "--type=A"], "--type is only valid for list"),
        (["diff", "--type=A"], "--type is only valid for list"),
        (["check", "--type=A", "--origin=sub"], 'invalid --origin "sub" (expected an absolute name such as example.com.)'),
        (["check", "--origin=sub", "--type=A"], 'invalid --origin "sub" (expected an absolute name such as example.com.)'),
        (["check"], "missing ZONE"),
        (["list"], "missing ZONE"),
        (["diff"], "missing OLD"),
        (["diff", "old"], "missing NEW"),
        (["list", "one", "two"], "too many arguments"),
        (["diff", "old", "new", "extra"], "too many arguments"),
        (["diff", "-", "-"], "standard input given twice"),
        (["check", "-", "-"], "standard input given twice"),
        (["check", "-", "zone", "-"], "standard input given twice"),
        (["list", "-", "extra"], "too many arguments"),
        (["diff", "-", "-", "extra"], "too many arguments"),
        (
            ["check", "--origin=example.com.", "--origin"],
            "--origin needs a value",
        ),
    ],
)
def test_parse_args_reports_exact_usage_error_and_precedence(
    argv: list[str], message: str
) -> None:
    with pytest.raises(UsageError) as error:
        parse_args(argv)

    assert str(error.value) == message
