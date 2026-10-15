"""Zone-file parsing and immutable record/zone models."""

from dataclasses import dataclass

from zonevet.lexer import Entry, LexError, tokenize
from zonevet.names import resolve_name
from zonevet.rdata import NameReference, RData, SOAFields, parse_rdata
from zonevet.text import quote
from zonevet.ttl import parse_ttl


@dataclass(frozen=True, slots=True)
class ZoneError(Exception):
    """A syntax error attributed to a physical source line."""

    line: int
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class Record:
    """One validated DNS record, retaining typed and source-oriented data."""

    owner: str
    ttl: int
    rtype: str
    rdata: RData
    line: int
    raw_owner: str | None
    owner_inherited: bool
    name_references: tuple[NameReference, ...]

    @property
    def type(self) -> str:
        """Return the record type using the conventional short attribute name."""
        return self.rtype

    @property
    def canonical_rdata(self) -> str:
        """Return the canonical text for the rdata portion."""
        return self.rdata.canonical

    @property
    def canonical(self) -> str:
        """Return the complete canonical record line."""
        return f"{self.owner} {self.ttl} IN {self.rtype} {self.rdata.canonical}"

    @property
    def targets(self) -> tuple[str, ...]:
        """Return resolved name targets used by semantic checks."""
        return self.rdata.targets

    @property
    def soa(self) -> SOAFields | None:
        """Return typed SOA fields when this is an SOA record."""
        return self.rdata.soa

    @property
    def raw_names(self) -> tuple[str, ...]:
        """Return explicit owner and rdata names in their source order."""
        return tuple(reference.raw for reference in self.name_references)


@dataclass(frozen=True, slots=True)
class Zone:
    """Parsed records and the apex captured at the first record."""

    records: tuple[Record, ...]
    apex: str | None

    @property
    def initial_apex(self) -> str | None:
        """Alias that emphasizes the apex does not follow later $ORIGIN changes."""
        return self.apex


def _zone_error(line: int, error: ValueError) -> ZoneError:
    return ZoneError(line, str(error))


def _directive_name(value: str, origin: str | None, line: int) -> str:
    if not value.endswith("."):
        raise ZoneError(
            line,
            f"invalid $ORIGIN {quote(value)} (expected an absolute name such as example.com.)",
        )
    try:
        return resolve_name(value, origin)
    except ValueError as error:
        raise _zone_error(line, error) from None


def _is_ascii_digit(value: str) -> bool:
    return bool(value) and "0" <= value[0] <= "9"


def _parse_record(
    entry: Entry,
    origin: str | None,
    default_ttl: int | None,
    previous_owner: str | None,
) -> tuple[Record, str]:
    tokens = entry.tokens
    index = 0
    raw_owner: str | None
    owner_reference: NameReference | None

    if entry.indented:
        if previous_owner is None:
            raise ZoneError(entry.line, "no previous owner")
        owner = previous_owner
        raw_owner = None
        owner_reference = None
        inherited = True
    else:
        owner_token = tokens[0]
        if owner_token.quoted:
            raise ZoneError(entry.line, "expected an owner name")
        raw_owner = owner_token.value
        if origin is None:
            raise ZoneError(entry.line, "no origin (add $ORIGIN or use --origin)")
        try:
            owner = resolve_name(raw_owner, origin, allow_wildcard=True)
        except ValueError as error:
            raise _zone_error(entry.line, error) from None
        owner_reference = NameReference(raw_owner, owner, owner_token.line, "owner")
        index = 1
        inherited = False

    if origin is None:
        raise ZoneError(entry.line, "no origin (add $ORIGIN or use --origin)")

    ttl: int | None = None
    class_seen = False

    while index < len(tokens):
        token = tokens[index]
        value = token.value
        upper = value.upper()
        if not token.quoted and ttl is None and _is_ascii_digit(value):
            try:
                ttl = parse_ttl(value)
            except ValueError as error:
                raise _zone_error(entry.line, error) from None
            index += 1
            continue
        if not token.quoted and upper in {"CS", "CH", "HS"}:
            raise ZoneError(entry.line, f"unsupported class {quote(upper)}")
        if not token.quoted and not class_seen and upper == "IN":
            class_seen = True
            index += 1
            continue
        break

    if index >= len(tokens):
        raise ZoneError(entry.line, "missing record type")

    type_token = tokens[index]
    if type_token.quoted:
        raise ZoneError(entry.line, f"unknown record type {quote(type_token.value)}")
    rtype = type_token.value.upper()
    if rtype not in {"A", "AAAA", "CNAME", "MX", "NS", "PTR", "SOA", "SRV", "TXT"}:
        raise ZoneError(entry.line, f"unknown record type {quote(type_token.value)}")
    index += 1

    if ttl is None:
        ttl = default_ttl
    if ttl is None:
        raise ZoneError(entry.line, "no TTL (add $TTL or give one)")

    try:
        rdata = parse_rdata(rtype, tokens[index:], origin)
    except ValueError as error:
        raise _zone_error(entry.line, error) from None

    references = (() if owner_reference is None else (owner_reference,)) + rdata.name_references
    record = Record(
        owner=owner,
        ttl=ttl,
        rtype=rtype,
        rdata=rdata,
        line=entry.line,
        raw_owner=raw_owner,
        owner_inherited=inherited,
        name_references=references,
    )
    return record, owner


def parse_zone(text: str, origin: str | None = None) -> Zone:
    """Parse a DNS master-format zone, stopping at its first syntax error."""
    current_origin = origin.lower() if origin is not None else None
    default_ttl: int | None = None
    previous_owner: str | None = None
    apex: str | None = None
    records: list[Record] = []

    try:
        entries = tokenize(text)
        for entry in entries:
            tokens = entry.tokens
            first = tokens[0]
            if not first.quoted and first.value.startswith("$"):
                directive = first.value[1:]
                if directive == "TTL":
                    if len(tokens) != 2 or tokens[1].quoted:
                        raise ZoneError(entry.line, 'expected "$TTL TTL"')
                    try:
                        default_ttl = parse_ttl(tokens[1].value)
                    except ValueError as error:
                        raise _zone_error(entry.line, error) from None
                    continue

                if directive == "ORIGIN":
                    if len(tokens) != 2 or tokens[1].quoted:
                        raise ZoneError(entry.line, 'expected "$ORIGIN NAME"')
                    current_origin = _directive_name(tokens[1].value, current_origin, entry.line)
                    continue

                raise ZoneError(
                    entry.line,
                    f"unknown directive {quote(first.value)}",
                )

            record, previous_owner = _parse_record(
                entry,
                current_origin,
                default_ttl,
                previous_owner,
            )
            if apex is None:
                apex = current_origin
            records.append(record)
    except LexError as error:
        raise ZoneError(error.line, error.message) from None

    return Zone(tuple(records), apex)
