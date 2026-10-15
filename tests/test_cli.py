"""End-to-end CLI examples, including the real UTF-8 byte channels."""

import io
import subprocess
import sys
from pathlib import Path

import pytest

from zonevet.cli import main

GOOD_ZONE = (
    "$ORIGIN example.com.\n"
    "$TTL 1h\n"
    "@       IN SOA ns1 hostmaster (\n"
    "            2024010101 ; serial\n"
    "            2h         ; refresh\n"
    "            15m        ; retry\n"
    "            2w         ; expire\n"
    "            1h )       ; minimum\n"
    "        IN NS   ns1\n"
    "        IN NS   ns2.example.net.\n"
    "        IN MX   10 mail\n"
    '        IN TXT  "v=spf1 mx -all" "say \\"hi\\""\n'
    "ns1     IN A    192.0.2.53\n"
    "mail    A       192.0.2.25\n"
    "www     300 IN  CNAME web\n"
    "web     IN AAAA 2001:0db8:0000:0000:0000:0000:0000:0001\n"
    "web     A       192.0.2.80\n"
    "_sip._tcp SRV 10 60 5060 mail\n"
)

GOOD_LIST = (
    "example.com. 3600 IN SOA ns1.example.com. hostmaster.example.com. "
    "2024010101 7200 900 1209600 3600\n"
    "example.com. 3600 IN NS ns1.example.com.\n"
    "example.com. 3600 IN NS ns2.example.net.\n"
    "example.com. 3600 IN MX 10 mail.example.com.\n"
    'example.com. 3600 IN TXT "v=spf1 mx -all" "say \\"hi\\""\n'
    "ns1.example.com. 3600 IN A 192.0.2.53\n"
    "mail.example.com. 3600 IN A 192.0.2.25\n"
    "www.example.com. 300 IN CNAME web.example.com.\n"
    "web.example.com. 3600 IN AAAA 2001:db8::1\n"
    "web.example.com. 3600 IN A 192.0.2.80\n"
    "_sip._tcp.example.com. 3600 IN SRV 10 60 5060 mail.example.com.\n"
)

GOOD_A_LIST = (
    "ns1.example.com. 3600 IN A 192.0.2.53\n"
    "mail.example.com. 3600 IN A 192.0.2.25\n"
    "web.example.com. 3600 IN A 192.0.2.80\n"
)

BAD_ZONE = """$ORIGIN example.com.
$TTL 300
www     CNAME   web
www     A       192.0.2.1
web     CNAME   www
@       MX      10 www
mail    A       192.0.2.25
mail    A       192.0.2.25
ns1     600 A   192.0.2.53
ns1     A       192.0.2.54
sub     NS      ns2
alias   CNAME   www.example.com
other.org. A    192.0.2.9
@       SOA     ns1 admin 1 600 900 1000 300
"""

BAD_CHECK = """bad.zone:3: ZC103 "www.example.com." has a CNAME and other data (line 4)
bad.zone:3: ZC105 CNAME loop: www.example.com. -> web.example.com. -> www.example.com.
bad.zone:3: ZC109 no NS record at the zone apex
bad.zone:6: ZC104 MX target "www.example.com." is a CNAME (line 3)
bad.zone:8: ZC102 duplicate of line 7
bad.zone:10: ZC107 RRset "ns1.example.com." A has different TTLs (600 on line 9, 300 on line 10)
bad.zone:11: ZC106 NS target "ns2.example.com." has no A or AAAA record
bad.zone:12: ZC111 "www.example.com" is relative and ends with the zone name (missing trailing dot?)
bad.zone:13: ZC108 "other.org." is outside the zone "example.com."
bad.zone:14: ZC101 SOA is not the first record
bad.zone:14: ZC110 SOA retry (900) is not smaller than refresh (600)
bad.zone:14: ZC110 SOA expire (1000) is not larger than refresh plus retry (1500)
12 problems in 1 file, 1 file checked
"""

NEW_ZONE = (
    "$ORIGIN example.com.\n"
    "$TTL 1h\n"
    "@ 3600 IN SOA ns1 hostmaster 2024010102 7200 900 1209600 3600\n"
    "@ NS ns1\n"
    "@ NS ns2.example.net.\n"
    "@ MX 10 mail\n"
    '@ TXT "v=spf1 mx -all" "say \\"hi\\""\n'
    "ns1 A 192.0.2.53\n"
    "www 600 IN CNAME web\n"
    "web IN AAAA 2001:0db8:0000:0000:0000:0000:0000:0001\n"
    "web A 192.0.2.81\n"
    "_sip._tcp SRV 10 60 5060 mail\n"
    "blog A 192.0.2.90\n"
)

DIFF_FORWARD = """+ blog.example.com. 3600 IN A 192.0.2.90
- mail.example.com. 3600 IN A 192.0.2.25
- web.example.com. 3600 IN A 192.0.2.80
+ web.example.com. 3600 IN A 192.0.2.81
~ www.example.com. CNAME web.example.com.: ttl 300 -> 600
serial 2024010101 -> 2024010102
5 changes
"""
DIFF_REVERSE = """- blog.example.com. 3600 IN A 192.0.2.90
+ mail.example.com. 3600 IN A 192.0.2.25
+ web.example.com. 3600 IN A 192.0.2.80
- web.example.com. 3600 IN A 192.0.2.81
~ www.example.com. CNAME web.example.com.: ttl 600 -> 300
serial 2024010102 -> 2024010101
5 changes
warning: the SOA serial did not increase (2024010101)
"""


def _main(argv: list[str], data: bytes = b"") -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    status = main(argv, stdin=io.BytesIO(data), stdout=stdout, stderr=stderr)
    return status, stdout.getvalue(), stderr.getvalue()


def _write_bytes(tmp_path: Path, filename: str, data: bytes) -> Path:
    path = tmp_path / filename
    path.write_bytes(data); return path


def _shown(path: Path | str) -> str:
    return str(path).replace("\\", "/")


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        ([], "missing command (check, list or diff)"),
        (["inspect"], 'unknown command "inspect"'),
        (["dÉf"], 'unknown command "d?f"'),
        (["check", "--help"], 'unknown option "--help"'),
        (["check", "--wat"], 'unknown option "--wat"'),
        (["check", "--origin"], "--origin needs a value"),
        (["check", "--origin", "sub"], 'invalid --origin "sub" (expected an absolute name such as example.com.)'),
        (["list", "--type=HINFO"], 'invalid --type "HINFO" (expected A, AAAA, CNAME, MX, NS, PTR, SOA, SRV or TXT)'),
        (["check", "--type=A"], "--type is only valid for list"),
        (["diff", "--type=A"], "--type is only valid for list"),
        (["check"], "missing ZONE"),
        (["list"], "missing ZONE"),
        (["diff"], "missing OLD"),
        (["diff", "old"], "missing NEW"),
        (["list", "one", "two"], "too many arguments"),
        (["diff", "old", "new", "extra"], "too many arguments"),
        (["diff", "-", "-"], "standard input given twice"),
    ],
)
def test_usage_errors_have_exact_stderr_and_no_stdout(argv: list[str], message: str) -> None:
    status, stdout, stderr = _main(argv)
    assert (status, stdout, stderr) == (2, "", f"zonevet: {message}\n")


def test_help_is_the_exact_three_lines_and_ends_in_lf() -> None:
    assert _main(["--help"]) == (0, (
        "usage: zonevet check [--origin NAME] ZONE...\n"
        "       zonevet list [--origin NAME] [--type TYPE] ZONE\n"
        "       zonevet diff [--origin NAME] OLD NEW\n"
    ), "")


def test_late_input_error_suppresses_output_and_normalizes_path(tmp_path: Path) -> None:
    first = _write_bytes(tmp_path, "first.zone", GOOD_ZONE.encode("utf-8"))
    missing = str(tmp_path / "missing.zone").replace("/", "\\")
    assert _main(["check", str(first), missing]) == (
        2, "", f"zonevet: {_shown(missing)}: cannot read the file\n"
    )


@pytest.mark.parametrize(
    ("argv", "source", "message"),
    [
        (["check", "-"], b"x A 192.0.2.1\n", "no origin (add $ORIGIN or use --origin)"),
        (
            ["check", "--origin", "x.org.", "-"],
            b"x A 192.0.2.1\n",
            "no TTL (add $TTL or give one)",
        ),
    ],
)
def test_check_stdin_reports_exact_syntax_finding(
    argv: list[str], source: bytes, message: str
) -> None:
    assert _main(argv, source) == (
        1,
        f"<stdin>:1: ZC001 {message}\n1 problem in 1 file, 1 file checked\n",
        "",
    )


def test_check_empty_and_multi_file_totals_and_list_output(tmp_path: Path) -> None:
    empty = _write_bytes(tmp_path, "empty.zone", b"")
    assert _main(["check", str(empty)]) == (
        1, f"{_shown(empty)}:1: ZC101 missing SOA record\n1 problem in 1 file, 1 file checked\n", ""
    )
    assert _main(["list", str(empty)]) == (0, "", "")
    second = _write_bytes(tmp_path, "second.zone", b"")
    assert _main(["check", str(empty), str(second)]) == (
        1,
        (
            f"{_shown(empty)}:1: ZC101 missing SOA record\n"
            f"{_shown(second)}:1: ZC101 missing SOA record\n"
            "2 problems in 2 files, 2 files checked\n"
        ),
        "",
    )


def test_check_good_worked_zone_reports_exact_success(tmp_path: Path, monkeypatch) -> None:
    good = _write_bytes(tmp_path, "good.zone", GOOD_ZONE.encode("utf-8"))
    monkeypatch.chdir(tmp_path)
    assert _main(["check", good.name]) == (0, "ok, 1 file checked\n", "")


def test_check_bad_worked_zone_matches_complete_output(tmp_path: Path, monkeypatch) -> None:
    bad = _write_bytes(tmp_path, "bad.zone", BAD_ZONE.encode("utf-8"))
    monkeypatch.chdir(tmp_path)
    assert _main(["check", bad.name]) == (1, BAD_CHECK, "")


def test_list_full_and_filtered_worked_zone_output(tmp_path: Path, monkeypatch) -> None:
    good = _write_bytes(tmp_path, "good.zone", GOOD_ZONE.encode("utf-8"))
    monkeypatch.chdir(tmp_path)
    assert _main(["list", good.name]) == (0, GOOD_LIST, "")
    assert _main(["list", "--type", "a", good.name]) == (0, GOOD_A_LIST, "")
    assert _main(["list", "--type=MX", good.name]) == (
        0, "example.com. 3600 IN MX 10 mail.example.com.\n", ""
    )


def test_list_and_diff_syntax_errors_have_exact_stderr(tmp_path: Path) -> None:
    source = b"$ORIGIN example.com.\n$TTL 60\nx A\n"
    bad = _write_bytes(tmp_path, "bad.zone", source)
    assert _main(["list", str(bad)]) == (
        1, "", f'zonevet: {_shown(bad)}:3: expected "A ADDRESS"\n'
    )
    good = _write_bytes(tmp_path, "new.zone", GOOD_ZONE.encode("utf-8"))
    assert _main(["diff", str(bad), str(good)]) == (
        1, "", f'zonevet: {_shown(bad)}:3: expected "A ADDRESS"\n'
    )


def test_diff_forward_and_reverse_worked_examples_are_exact(tmp_path: Path, monkeypatch) -> None:
    old = _write_bytes(tmp_path, "good.zone", GOOD_ZONE.encode("utf-8"))
    new = _write_bytes(tmp_path, "new.zone", NEW_ZONE.encode("utf-8"))
    monkeypatch.chdir(tmp_path)
    assert _main(["diff", old.name, new.name]) == (1, DIFF_FORWARD, "")
    assert _main(["diff", new.name, old.name]) == (1, DIFF_REVERSE, "")


def test_diff_identical_and_stdin_operands_report_no_changes(tmp_path: Path) -> None:
    zone = b"$ORIGIN example.com.\n$TTL 60\n@ SOA ns host 1 600 60 2000 300\n"
    old = _write_bytes(tmp_path, "old.zone", zone)
    new = _write_bytes(tmp_path, "new.zone", zone)
    assert _main(["diff", str(old), str(new)]) == (0, "no changes\n", "")
    assert _main(["diff", "-", str(new)], zone) == (0, "no changes\n", "")
    assert _main(["list", "-"], zone) == (
        0,
        "example.com. 60 IN SOA ns.example.com. host.example.com. 1 600 60 2000 300\n",
        "",
    )


def _assert_entrypoint(
    argv: list[str], data: bytes, expected: tuple[int, bytes, bytes]
) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "zonevet", *argv], input=data, capture_output=True,
        cwd=Path(__file__).resolve().parents[1], timeout=30, check=False,
    )
    assert (result.returncode, result.stdout, result.stderr) == expected


def test_entrypoint_reads_stdin_bytes_and_preserves_exact_utf8_errors_and_bom() -> None:
    _assert_entrypoint(
        ["list", "-"], b"\xff", (2, b"", b"zonevet: <stdin>: input is not valid UTF-8\n")
    )
    bom = b"\xef\xbb\xbf$ORIGIN example.com.\n$TTL 60\n@ SOA ns host 1 600 60 2000 300\n"
    _assert_entrypoint(
        ["list", "-"], bom,
        (0, b"example.com. 60 IN SOA ns.example.com. host.example.com. 1 600 60 2000 300\n", b""),
    )


def test_entrypoint_reads_file_bytes_and_preserves_exact_utf8_errors_and_bom(tmp_path: Path) -> None:
    bad = _write_bytes(tmp_path, "invalid.zone", b"$ORIGIN example.com.\n\xff")
    _assert_entrypoint(
        ["list", str(bad)], b"",
        (2, b"", f"zonevet: {_shown(bad)}: input is not valid UTF-8\n".encode()),
    )
    good = _write_bytes(
        tmp_path, "bom.zone",
        b"\xef\xbb\xbf$ORIGIN example.com.\n$TTL 60\n@ SOA ns host 1 600 60 2000 300\n",
    )
    _assert_entrypoint(
        ["list", str(good)], b"",
        (0, b"example.com. 60 IN SOA ns.example.com. host.example.com. 1 600 60 2000 300\n", b""),
    )
