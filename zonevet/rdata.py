"""Typed resource-data parsing and canonical DNS rendering."""

from dataclasses import dataclass
from typing import TypeAlias

from zonevet.ipaddr import format_ipv6, parse_ipv4, parse_ipv6
from zonevet.lexer import Token
from zonevet.names import resolve_name
from zonevet.text import quote
from zonevet.ttl import parse_ttl

Value: TypeAlias = str | int


@dataclass(frozen=True, slots=True)
class NameReference:
    """A name as written in the source and its resolved absolute form."""

    raw: str
    resolved: str
    line: int
    field: str


@dataclass(frozen=True, slots=True)
class SOAFields:
    """Typed SOA values, with all time fields represented in seconds."""

    mname: str
    rname: str
    serial: int
    refresh: int
    retry: int
    expire: int
    minimum: int


@dataclass(frozen=True, slots=True)
class RData:
    """Parsed, typed rdata and its canonical representation."""

    rtype: str
    values: tuple[Value, ...]
    canonical: str
    name_references: tuple[NameReference, ...] = ()
    targets: tuple[str, ...] = ()
    soa: SOAFields | None = None

    @property
    def type(self) -> str:
        """Return the record type using the conventional short attribute name."""
        return self.rtype

    @property
    def raw_names(self) -> tuple[str, ...]:
        """Return explicitly written name values in source order."""
        return tuple(reference.raw for reference in self.name_references)


def _token_value(token: Token) -> str:
    return token.value


def _token_line(token: Token) -> int:
    return token.line


def _invalid_number(value: str, low: int, high: int) -> ValueError:
    return ValueError(
        f"invalid number {quote(value)} (expected {low} to {high})"
    )


def _parse_number(value: str, low: int, high: int) -> int:
    if not 1 <= len(value) <= 10 or any(character < "0" or character > "9" for character in value):
        raise _invalid_number(value, low, high)
    number = int(value)
    if not low <= number <= high:
        raise _invalid_number(value, low, high)
    return number


def _name(token: Token, origin: str | None, field: str) -> NameReference:
    resolved = resolve_name(token.value, origin)
    return NameReference(token.value, resolved, token.line, field)


def _expected(rtype: str, description: str) -> ValueError:
    return ValueError(f'expected "{rtype} {description}"')


def _require_count(rtype: str, tokens: tuple[Token, ...], count: int, description: str) -> None:
    if len(tokens) != count:
        raise _expected(rtype, description)


def _canonical_txt(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_rdata(rtype: str, tokens: tuple[Token, ...] | list[Token], origin: str | None) -> RData:
    """Parse one record's rdata values and return typed values plus canonical text.

    Tokens are validated from left to right after the record's arity is checked.
    Name references keep their original spelling for source-oriented diagnostics.
    """
    normalized_type = rtype.upper()
    values = tuple(tokens)

    if normalized_type == "A":
        _require_count(normalized_type, values, 1, "ADDRESS")
        address = parse_ipv4(_token_value(values[0]))
        return RData(normalized_type, (address,), address)

    if normalized_type == "AAAA":
        _require_count(normalized_type, values, 1, "ADDRESS")
        address = format_ipv6(parse_ipv6(_token_value(values[0])))
        return RData(normalized_type, (address,), address)

    if normalized_type in {"CNAME", "NS", "PTR"}:
        _require_count(normalized_type, values, 1, "NAME")
        reference = _name(values[0], origin, "target")
        return RData(
            normalized_type,
            (reference.resolved,),
            reference.resolved,
            (reference,),
            (reference.resolved,),
        )

    if normalized_type == "MX":
        _require_count(normalized_type, values, 2, "PREFERENCE NAME")
        preference = _parse_number(_token_value(values[0]), 0, 65535)
        reference = _name(values[1], origin, "target")
        return RData(
            normalized_type,
            (preference, reference.resolved),
            f"{preference} {reference.resolved}",
            (reference,),
            (reference.resolved,),
        )

    if normalized_type == "SRV":
        _require_count(normalized_type, values, 4, "PRIORITY WEIGHT PORT TARGET")
        priority = _parse_number(_token_value(values[0]), 0, 65535)
        weight = _parse_number(_token_value(values[1]), 0, 65535)
        port = _parse_number(_token_value(values[2]), 0, 65535)
        reference = _name(values[3], origin, "target")
        return RData(
            normalized_type,
            (priority, weight, port, reference.resolved),
            f"{priority} {weight} {port} {reference.resolved}",
            (reference,),
            (reference.resolved,),
        )

    if normalized_type == "TXT":
        if not values:
            raise _expected(normalized_type, "STRING...")
        strings: list[str] = []
        for token in values:
            string = _token_value(token)
            try:
                length = len(string.encode("utf-8"))
            except UnicodeEncodeError:
                raise ValueError("string longer than 255 bytes") from None
            if length > 255:
                raise ValueError("string longer than 255 bytes")
            strings.append(string)
        return RData(
            normalized_type,
            tuple(strings),
            " ".join(_canonical_txt(string) for string in strings),
        )

    if normalized_type == "SOA":
        _require_count(
            normalized_type,
            values,
            7,
            "MNAME RNAME SERIAL REFRESH RETRY EXPIRE MINIMUM",
        )
        mname = _name(values[0], origin, "mname")
        rname = _name(values[1], origin, "rname")
        serial = _parse_number(_token_value(values[2]), 0, 4_294_967_295)
        refresh = parse_ttl(_token_value(values[3]))
        retry = parse_ttl(_token_value(values[4]))
        expire = parse_ttl(_token_value(values[5]))
        minimum = parse_ttl(_token_value(values[6]))
        soa = SOAFields(
            mname.resolved,
            rname.resolved,
            serial,
            refresh,
            retry,
            expire,
            minimum,
        )
        canonical = (
            f"{soa.mname} {soa.rname} {soa.serial} {soa.refresh} "
            f"{soa.retry} {soa.expire} {soa.minimum}"
        )
        return RData(
            normalized_type,
            (
                soa.mname,
                soa.rname,
                soa.serial,
                soa.refresh,
                soa.retry,
                soa.expire,
                soa.minimum,
            ),
            canonical,
            (mname, rname),
            (),
            soa,
        )

    raise ValueError(f"unknown record type {quote(rtype)}")
