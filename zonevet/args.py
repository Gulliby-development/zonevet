"""Handwritten command-line argument parsing for zonevet."""

from collections.abc import Sequence
from dataclasses import dataclass

from zonevet.names import resolve_name
from zonevet.text import quote

USAGE = (
    "usage: zonevet check [--origin NAME] ZONE...\n"
    "       zonevet list [--origin NAME] [--type TYPE] ZONE\n"
    "       zonevet diff [--origin NAME] OLD NEW"
)

_RECORD_TYPES = frozenset({"A", "AAAA", "CNAME", "MX", "NS", "PTR", "SOA", "SRV", "TXT"})


class UsageError(ValueError):
    """A command-line usage error with the message to show after zonevet:."""


@dataclass(frozen=True)
class ParsedArgs:
    """Validated command, options and file operands."""

    command: str
    origin: str | None
    record_type: str | None
    files: tuple[str, ...]


def parse_args(argv: Sequence[str]) -> ParsedArgs:
    """Parse arguments, raising UsageError for the first usage error.

    --help is intentionally special only when it is the sole argument.
    Option scanning precedes semantic option and operand validation so the
    latter follow the command-line grammar's prescribed precedence.
    """
    if not argv:
        raise UsageError("missing command (check, list or diff)")
    if len(argv) == 1 and argv[0] == "--help":
        return ParsedArgs("help", None, None, ())

    command = argv[0]
    if command not in {"check", "list", "diff"}:
        raise UsageError(f"unknown command {quote(command)}")

    raw_origin: str | None = None
    raw_type: str | None = None
    files: list[str] = []
    index = 1

    while index < len(argv):
        argument = argv[index]
        if argument == "--origin" or argument == "--type":
            option = argument
            if index + 1 >= len(argv):
                if option == "--origin":
                    raise UsageError("--origin needs a value")
                raise UsageError("--type needs a value")
            value = argv[index + 1]
            index += 2
            if option == "--origin":
                raw_origin = value
            else:
                raw_type = value
            continue

        if argument.startswith("--origin="):
            raw_origin = argument[len("--origin=") :]
        elif argument.startswith("--type="):
            raw_type = argument[len("--type=") :]
        elif argument.startswith("-") and argument != "-":
            raise UsageError(f"unknown option {quote(argument)}")
        else:
            files.append(argument)
        index += 1

    origin: str | None = None
    if raw_origin is not None:
        normalized_origin = raw_origin.lower()
        try:
            if not raw_origin.endswith("."):
                raise ValueError
            origin = resolve_name(raw_origin, None)
        except ValueError:
            raise UsageError(
                f"invalid --origin {quote(normalized_origin)} "
                "(expected an absolute name such as example.com.)"
            ) from None

    record_type: str | None = None
    if raw_type is not None:
        record_type = raw_type.upper()
        if not raw_type.isascii() or record_type not in _RECORD_TYPES:
            raise UsageError(
                f"invalid --type {quote(raw_type)} "
                "(expected A, AAAA, CNAME, MX, NS, PTR, SOA, SRV or TXT)"
            )

    if record_type is not None and command != "list":
        raise UsageError("--type is only valid for list")

    if command == "check":
        if not files:
            raise UsageError("missing ZONE")
    elif command == "list":
        if not files:
            raise UsageError("missing ZONE")
        if len(files) > 1:
            raise UsageError("too many arguments")
    else:
        if not files:
            raise UsageError("missing OLD")
        if len(files) == 1:
            raise UsageError("missing NEW")
        if len(files) > 2:
            raise UsageError("too many arguments")

    if sum(file == "-" for file in files) > 1:
        raise UsageError("standard input given twice")

    return ParsedArgs(command, origin, record_type, tuple(files))
