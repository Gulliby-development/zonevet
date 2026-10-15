"""Exact text rendering for check, list and diff results."""

from collections.abc import Sequence

from zonevet.checks import Finding
from zonevet.diffing import DiffResult
from zonevet.text import display, plural
from zonevet.zone import Zone


def format_usage(usage: str) -> str:
    """Return the help text with its required final LF."""
    return usage + "\n"


def format_check(
    results: Sequence[tuple[str, Sequence[Finding]]], files_checked: int
) -> str:
    """Render findings in file order followed by the exact aggregate summary."""
    lines: list[str] = []
    total_findings = 0
    files_with_findings = 0

    for path, findings in results:
        shown_path = display(path)
        if findings:
            files_with_findings += 1
        total_findings += len(findings)
        lines.extend(
            f"{shown_path}:{finding.line}: {finding.code} {finding.message}"
            for finding in findings
        )

    if total_findings:
        lines.append(
            f"{total_findings} {plural(total_findings, 'problem')} in "
            f"{files_with_findings} {plural(files_with_findings, 'file')}, "
            f"{files_checked} {plural(files_checked, 'file')} checked"
        )
    else:
        lines.append(f"ok, {files_checked} {plural(files_checked, 'file')} checked")
    return "\n".join(lines) + "\n"


def format_list(zone: Zone, record_type: str | None = None) -> str:
    """Render canonical records in source order, optionally filtered by type."""
    lines = [
        record.canonical
        for record in zone.records
        if record_type is None or record.rtype == record_type
    ]
    return "" if not lines else "\n".join(lines) + "\n"


def format_diff(result: DiffResult) -> str:
    """Render sorted record changes, serial details and the final summary."""
    lines: list[str] = []
    for change in result.changes:
        if change.kind == "added":
            assert change.new is not None
            lines.append(f"+ {change.new.canonical}")
        elif change.kind == "removed":
            assert change.old is not None
            lines.append(f"- {change.old.canonical}")
        else:
            assert change.old is not None and change.new is not None
            owner, rtype, rdata = change.key
            lines.append(
                f"~ {owner} {rtype} {rdata}: ttl {change.old.ttl} -> {change.new.ttl}"
            )

    if result.serial_transition is not None:
        old_serial, new_serial = result.serial_transition
        lines.append(f"serial {old_serial} -> {new_serial}")

    if result.record_change_count:
        count = result.record_change_count
        lines.append(f"{count} {plural(count, 'change')}")
    else:
        lines.append("no changes")

    if result.warning_serial is not None:
        lines.append(
            "warning: the SOA serial did not increase "
            f"({result.warning_serial})"
        )
    return "\n".join(lines) + "\n"
