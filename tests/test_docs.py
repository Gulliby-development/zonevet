"""Documentation test."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

GOOD_ZONE = """$ORIGIN example.com.
$TTL 1h
@       IN SOA ns1 hostmaster (
            2024010101 ; serial
            2h         ; refresh
            15m        ; retry
            2w         ; expire
            1h )       ; minimum
        IN NS   ns1
        IN NS   ns2.example.net.
        IN MX   10 mail
        IN TXT  "v=spf1 mx -all" "say \\"hi\\""
ns1     IN A    192.0.2.53
mail    A       192.0.2.25
www     300 IN  CNAME web
web     IN AAAA 2001:0db8:0000:0000:0000:0000:0000:0001
web     A       192.0.2.80
_sip._tcp SRV 10 60 5060 mail
"""

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

GOOD_LIST = """example.com. 3600 IN SOA ns1.example.com. hostmaster.example.com. 2024010101 7200 900 1209600 3600
example.com. 3600 IN NS ns1.example.com.
example.com. 3600 IN NS ns2.example.net.
example.com. 3600 IN MX 10 mail.example.com.
example.com. 3600 IN TXT "v=spf1 mx -all" "say \\"hi\\""
ns1.example.com. 3600 IN A 192.0.2.53
mail.example.com. 3600 IN A 192.0.2.25
www.example.com. 300 IN CNAME web.example.com.
web.example.com. 3600 IN AAAA 2001:db8::1
web.example.com. 3600 IN A 192.0.2.80
_sip._tcp.example.com. 3600 IN SRV 10 60 5060 mail.example.com.
"""

GOOD_A_LIST = """ns1.example.com. 3600 IN A 192.0.2.53
mail.example.com. 3600 IN A 192.0.2.25
web.example.com. 3600 IN A 192.0.2.80
"""

DIFF_FORWARD = """+ blog.example.com. 3600 IN A 192.0.2.90
- mail.example.com. 3600 IN A 192.0.2.25
- web.example.com. 3600 IN A 192.0.2.80
+ web.example.com. 3600 IN A 192.0.2.81
~ www.example.com. CNAME web.example.com.: ttl 300 -> 600
serial 2024010101 -> 2024010102
5 changes
"""

DIFF_REVERSE_END = """serial 2024010102 -> 2024010101
5 changes
warning: the SOA serial did not increase (2024010101)"""

USAGE = """usage: zonevet check [--origin NAME] ZONE...
       zonevet list [--origin NAME] [--type TYPE] ZONE
       zonevet diff [--origin NAME] OLD NEW"""

EXPECTED_FENCES = [
    ("text", "pip install ."),
    ("text", USAGE),
    ("zone", GOOD_ZONE[:-1]),
    ("zone", BAD_ZONE[:-1]),
    ("text", "ok, 1 file checked"),
    ("text", BAD_CHECK[:-1]),
    ("text", GOOD_LIST[:-1]),
    (
        "text",
        """ns1.example.com. 3600 IN A 192.0.2.53
mail.example.com. 3600 IN A 192.0.2.25
web.example.com. 3600 IN A 192.0.2.80""",
    ),
    ("text", DIFF_FORWARD[:-1]),
    ("text", DIFF_REVERSE_END),
    ("text", "pytest -q" + chr(10) + "ruff check ."),
]

EXPECTED_SOURCE_FILES = {
    "__init__.py", "__main__.py", "args.py", "checks.py", "cli.py", "diffing.py",
    "ipaddr.py", "lexer.py", "names.py", "rdata.py", "report.py", "text.py", "ttl.py", "zone.py",
}
EXPECTED_TEST_FILES = {
    "test_args.py", "test_checks.py", "test_cli.py", "test_diffing.py", "test_docs.py",
    "test_ipaddr.py", "test_lexer.py", "test_names.py", "test_rdata.py", "test_report.py",
    "test_text.py", "test_ttl.py", "test_zone.py",
}

@pytest.fixture(scope="module")
def readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _fenced_blocks(document: str) -> list[tuple[str, str]]:
    fence = chr(96) * 3
    blocks = []
    for block in document.split(fence)[1::2]:
        language, body = block.split("\n", 1)
        blocks.append((language, body.rsplit("\n", 1)[0]))
    return blocks


def test_readme_has_install_heading(readme: str) -> None:
    assert "## Install" in readme.splitlines()


def test_readme_has_usage_heading(readme: str) -> None:
    assert "## Usage" in readme.splitlines()


def test_readme_has_zone_files_heading(readme: str) -> None:
    assert "## Zone files" in readme.splitlines()


def test_readme_has_checks_heading(readme: str) -> None:
    assert "## Checks" in readme.splitlines()


def test_readme_has_exit_codes_heading(readme: str) -> None:
    assert "## Exit codes" in readme.splitlines()


def test_readme_has_development_heading_and_required_commands(readme: str) -> None:
    assert "## Development" in readme.splitlines()
    assert "python -m zonevet ARGS" in readme
    assert "pytest -q" in readme
    assert "ruff check ." in readme


def test_readme_contains_only_the_prescribed_example_blocks(readme: str) -> None:
    assert _fenced_blocks(readme) == EXPECTED_FENCES


def test_mit_license_contains_complete_terms_and_holder() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert license_text == """MIT License

Copyright (c) 2026 Gulliby-development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _parametrize_case_count(decorator: ast.expr, bindings: dict[str, ast.expr]) -> int:
    if not isinstance(decorator, ast.Call):
        return 1
    if not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "parametrize":
        return 1
    if len(decorator.args) > 1:
        argvalues = decorator.args[1]
    else:
        argvalues = next(
            (keyword.value for keyword in decorator.keywords if keyword.arg == "argvalues"),
            None,
        )
    if isinstance(argvalues, ast.Name):
        argvalues = bindings.get(argvalues.id, argvalues)
    assert isinstance(argvalues, (ast.List, ast.Tuple))
    return len(argvalues.elts)


def _written_test_case_count() -> int:
    count = 0
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"))
        bindings = {}
        for statement in module.body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = statement.value
            elif (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.value is not None
            ):
                bindings[statement.target.id] = statement.value
        for node in ast.walk(module):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                count += math.prod(
                    _parametrize_case_count(decorator, bindings) for decorator in node.decorator_list
                )
    return count


def test_inventory_file_counts_and_line_budgets() -> None:
    source_files = {path.name for path in (ROOT / "zonevet").glob("*.py")}
    test_files = {path.name for path in (ROOT / "tests").glob("*.py")}
    assert source_files == EXPECTED_SOURCE_FILES
    assert test_files == EXPECTED_TEST_FILES
    assert len(source_files) == 14
    assert len(test_files) == 13
    assert all(
        len(path.read_text(encoding="utf-8").splitlines()) < 400
        for path in (ROOT / "zonevet").glob("*.py")
    )
    assert len(Path(__file__).read_text(encoding="utf-8").splitlines()) < 300
    assert all(
        len(path.read_text(encoding="utf-8").splitlines()) < 310
        for path in (ROOT / "tests").glob("*.py")
    )
    assert _written_test_case_count() >= 200


def test_manifest_keeps_the_scaffold_project_and_tool_settings() -> None:
    manifest = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert manifest == """[project]
name = "zonevet"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
"""
