"""Offline command-line application for checking, listing and diffing zones."""

import sys
from collections.abc import Sequence
from typing import BinaryIO, TextIO

from zonevet.args import USAGE, ParsedArgs, UsageError, parse_args
from zonevet.checks import Finding, check_zone
from zonevet.diffing import diff_zones
from zonevet.report import format_check, format_diff, format_list, format_usage
from zonevet.text import display
from zonevet.zone import Zone, ZoneError, parse_zone


class _InputError(Exception):
    """A file read or UTF-8 decoding error with its displayed source name."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.message = message


def _read_operand(path: str, stdin: BinaryIO) -> tuple[str, str]:
    shown_path = "<stdin>" if path == "-" else display(path)
    try:
        if path == "-":
            data = stdin.read()
        else:
            with open(path, "rb") as source:
                data = source.read()
    except (OSError, ValueError):
        raise _InputError(shown_path, "cannot read the file") from None

    try:
        return shown_path, data.decode("utf-8")
    except UnicodeDecodeError:
        raise _InputError(shown_path, "input is not valid UTF-8") from None


def _parse_source(path: str, source: str, origin: str | None) -> Zone:
    return parse_zone(source, origin)


def _write(stream: TextIO, value: str) -> None:
    stream.write(value)


def _syntax_message(path: str, error: ZoneError) -> str:
    return f"zonevet: {display(path)}:{error.line}: {error.message}"


def _run_check(args: ParsedArgs, sources: Sequence[tuple[str, str]], stdout: TextIO) -> int:
    results: list[tuple[str, list[Finding]]] = []
    for path, source in sources:
        try:
            zone = _parse_source(path, source, args.origin)
        except ZoneError as error:
            findings = [Finding(error.line, "ZC001", error.message)]
        else:
            findings = check_zone(zone)
        results.append((path, findings))

    _write(stdout, format_check(results, len(sources)))
    return 1 if any(findings for _, findings in results) else 0


def main(
    argv: Sequence[str],
    stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run zonevet with injectable binary input and text output streams."""
    output = sys.stdout if stdout is None else stdout
    errors = sys.stderr if stderr is None else stderr
    binary_input = sys.stdin.buffer if stdin is None else stdin

    try:
        args = parse_args(argv)
    except UsageError as error:
        _write(errors, f"zonevet: {error}\n")
        return 2

    if args.command == "help":
        _write(output, format_usage(USAGE))
        return 0

    sources: list[tuple[str, str]] = []
    try:
        for path in args.files:
            sources.append(_read_operand(path, binary_input))
    except _InputError as error:
        _write(errors, f"zonevet: {error.path}: {error.message}\n")
        return 2

    if args.command == "check":
        return _run_check(args, sources, output)

    if args.command == "list":
        path, source = sources[0]
        try:
            zone = _parse_source(path, source, args.origin)
        except ZoneError as error:
            _write(errors, _syntax_message(path, error) + "\n")
            return 1
        _write(output, format_list(zone, args.record_type))
        return 0

    old_path, old_source = sources[0]
    new_path, new_source = sources[1]
    try:
        old_zone = _parse_source(old_path, old_source, args.origin)
    except ZoneError as error:
        _write(errors, _syntax_message(old_path, error) + "\n")
        return 1
    try:
        new_zone = _parse_source(new_path, new_source, args.origin)
    except ZoneError as error:
        _write(errors, _syntax_message(new_path, error) + "\n")
        return 1

    result = diff_zones(old_zone, new_zone)
    _write(output, format_diff(result))
    return 1 if result.has_changes else 0
