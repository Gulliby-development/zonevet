"""Semantic checks for parsed DNS zones."""

from dataclasses import dataclass

from zonevet.names import in_zone
from zonevet.text import quote
from zonevet.zone import Record, Zone


@dataclass(frozen=True, slots=True)
class Finding:
    """One stable, source-attributed semantic diagnostic."""

    line: int
    code: str
    message: str


def _first_by_owner(records: tuple[Record, ...], rtype: str) -> dict[str, Record]:
    found: dict[str, Record] = {}
    for record in records:
        if record.rtype == rtype:
            found.setdefault(record.owner, record)
    return found


def _cname_loops(first_cname: dict[str, Record]) -> list[Finding]:
    """Find cycles in the first-CNAME graph without recursive traversal."""
    state: dict[str, int] = {}
    findings: list[Finding] = []

    for start in first_cname:
        if state.get(start, 0) != 0:
            continue
        path: list[str] = []
        positions: dict[str, int] = {}
        current = start

        while current in first_cname and state.get(current, 0) == 0:
            state[current] = 1
            positions[current] = len(path)
            path.append(current)
            current = first_cname[current].targets[0]

        if current in positions:
            cycle = path[positions[current] :]
            first_owner = min(cycle, key=lambda owner: first_cname[owner].line)
            chain = [first_owner]
            next_owner = first_cname[first_owner].targets[0]
            while next_owner != first_owner:
                chain.append(next_owner)
                next_owner = first_cname[next_owner].targets[0]
            chain.append(first_owner)
            owner_record = first_cname[first_owner]
            findings.append(
                Finding(
                    owner_record.line,
                    "ZC105",
                    "CNAME loop: " + " -> ".join(chain),
                )
            )

        for owner in path:
            state[owner] = 2

    return findings


def _trailing_dot_findings(zone: Zone) -> list[Finding]:
    apex = zone.apex
    if apex is None or apex == ".":
        return []
    apex_text = apex[:-1].lower()
    findings: list[Finding] = []

    for record in zone.records:
        for reference in record.name_references:
            if reference.raw.endswith("."):
                continue
            if reference.field == "owner" and (record.owner_inherited or reference.raw == "@"):
                continue
            if reference.field == "target" and record.rtype not in {
                "CNAME", "NS", "PTR", "MX", "SRV"
            }:
                continue
            raw = reference.raw.lower()
            if raw == apex_text or raw.endswith("." + apex_text):
                findings.append(
                    Finding(
                        reference.line,
                        "ZC111",
                        f"{quote(reference.raw)} is relative and ends with the zone name "
                        "(missing trailing dot?)",
                    )
                )
    return findings


def _ipv4_target_findings(zone: Zone) -> list[Finding]:
    findings: list[Finding] = []
    target_types = {"CNAME", "NS", "MX", "SRV"}

    for record in zone.records:
        if record.rtype not in target_types:
            continue
        for reference in record.name_references:
            if reference.field != "target":
                continue
            parts = reference.raw.removesuffix(".").split(".")
            if len(parts) != 4 or any(
                not 1 <= len(part) <= 3
                or any(character < "0" or character > "9" for character in part)
                for part in parts
            ):
                continue
            findings.append(
                Finding(
                    reference.line,
                    "ZC112",
                    f"{record.rtype} target {quote(reference.raw)} looks like an IPv4 address "
                    "(use a host name)",
                )
            )
    return findings


def check_zone(zone: Zone) -> list[Finding]:
    """Return all specified semantic findings in stable report order."""
    records = zone.records
    if not records:
        return [Finding(1, "ZC101", "missing SOA record")]

    findings: list[Finding] = []
    soa_records = [record for record in records if record.rtype == "SOA"]
    if not soa_records:
        findings.append(Finding(1, "ZC101", "missing SOA record"))
    else:
        first_soa = soa_records[0]
        if records[0] is not first_soa:
            findings.append(Finding(first_soa.line, "ZC101", "SOA is not the first record"))
        for record in soa_records[1:]:
            findings.append(Finding(record.line, "ZC101", "more than one SOA record"))

    first_records: dict[tuple[str, str, str], Record] = {}
    for record in records:
        key = (record.owner, record.rtype, record.canonical_rdata)
        previous = first_records.get(key)
        if previous is None:
            first_records[key] = record
        else:
            findings.append(
                Finding(record.line, "ZC102", f"duplicate of line {previous.line}")
            )

    records_by_owner: dict[str, list[Record]] = {}
    for record in records:
        records_by_owner.setdefault(record.owner, []).append(record)
    first_cname = _first_by_owner(records, "CNAME")

    for owner, owner_records in records_by_owner.items():
        cnames = [record for record in owner_records if record.rtype == "CNAME"]
        other_data = [record for record in owner_records if record.rtype != "CNAME"]
        if cnames and other_data:
            first = cnames[0]
            findings.append(
                Finding(
                    first.line,
                    "ZC103",
                    f"{quote(owner)} has a CNAME and other data (line {other_data[0].line})",
                )
            )
        if len(cnames) > 1:
            findings.append(
                Finding(
                    cnames[1].line,
                    "ZC103",
                    f"second CNAME at {quote(owner)}",
                )
            )

    for record in records:
        if record.rtype not in {"NS", "MX", "SRV"}:
            continue
        for target in record.targets:
            cname = first_cname.get(target)
            if target != "." and cname is not None:
                findings.append(
                    Finding(
                        record.line,
                        "ZC104",
                        f"{record.rtype} target {quote(target)} is a CNAME (line {cname.line})",
                    )
                )

    findings.extend(_cname_loops(first_cname))

    addresses: set[str] = set()
    for record in records:
        if record.rtype in {"A", "AAAA"}:
            addresses.add(record.owner)
    if zone.apex is not None:
        for record in records:
            if record.rtype not in {"NS", "MX", "SRV"}:
                continue
            for target in record.targets:
                if (
                    target != "."
                    and in_zone(target, zone.apex)
                    and target not in first_cname
                    and target not in addresses
                ):
                    findings.append(
                        Finding(
                            record.line,
                            "ZC106",
                            f"{record.rtype} target {quote(target)} has no A or AAAA record",
                        )
                    )

    rrsets: dict[tuple[str, str], list[Record]] = {}
    for record in records:
        rrsets.setdefault((record.owner, record.rtype), []).append(record)
    for (owner, rtype), rrset in rrsets.items():
        first = rrset[0]
        differing = next((record for record in rrset[1:] if record.ttl != first.ttl), None)
        if differing is not None:
            findings.append(
                Finding(
                    differing.line,
                    "ZC107",
                    f"RRset {quote(owner)} {rtype} has different TTLs "
                    f"({first.ttl} on line {first.line}, {differing.ttl} on line {differing.line})",
                )
            )

    if zone.apex is not None:
        for record in records:
            if not in_zone(record.owner, zone.apex):
                findings.append(
                    Finding(
                        record.line,
                        "ZC108",
                        f"{quote(record.owner)} is outside the zone {quote(zone.apex)}",
                    )
                )

        if not any(record.rtype == "NS" and record.owner == zone.apex for record in records):
            findings.append(
                Finding(records[0].line, "ZC109", "no NS record at the zone apex")
            )

    if soa_records and soa_records[0].soa is not None:
        record = soa_records[0]
        soa = record.soa
        if soa.retry >= soa.refresh:
            findings.append(
                Finding(
                    record.line,
                    "ZC110",
                    f"SOA retry ({soa.retry}) is not smaller than refresh ({soa.refresh})",
                )
            )
        if soa.expire <= soa.refresh + soa.retry:
            findings.append(
                Finding(
                    record.line,
                    "ZC110",
                    f"SOA expire ({soa.expire}) is not larger than refresh plus retry "
                    f"({soa.refresh + soa.retry})",
                )
            )

    findings.extend(_trailing_dot_findings(zone))
    findings.extend(_ipv4_target_findings(zone))
    return sorted(findings, key=lambda finding: (finding.line, finding.code))
