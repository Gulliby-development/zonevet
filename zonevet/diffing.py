"""First-key record and serial comparison for DNS zones."""

from dataclasses import dataclass

from zonevet.zone import Record, Zone

RecordKey = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class DiffChange:
    """One sorted non-SOA record addition, removal or TTL-only change."""

    kind: str
    key: RecordKey
    old: Record | None
    new: Record | None


@dataclass(frozen=True, slots=True)
class DiffResult:
    """Structured differences, keeping serial changes separate from record counts."""

    changes: tuple[DiffChange, ...]
    serial_transition: tuple[int, int] | None
    warning_serial: int | None

    @property
    def record_change_count(self) -> int:
        """Return the number of changed non-SOA keys."""
        return len(self.changes)

    @property
    def has_changes(self) -> bool:
        """Return whether records or the first SOA serial differ."""
        return bool(self.changes) or self.serial_transition is not None

    @property
    def record_changes(self) -> tuple[DiffChange, ...]:
        """Alias for changes, clarifying that SOA transitions are not included."""
        return self.changes


def _first_records(zone: Zone) -> dict[RecordKey, Record]:
    first: dict[RecordKey, Record] = {}
    for record in zone.records:
        if record.rtype == "SOA":
            continue
        key = (record.owner, record.rtype, record.canonical_rdata)
        first.setdefault(key, record)
    return first


def _first_soa(zone: Zone) -> Record | None:
    return next((record for record in zone.records if record.rtype == "SOA"), None)


def diff_zones(old_zone: Zone, new_zone: Zone) -> DiffResult:
    """Compare first non-SOA records by canonical key and first-SOA serials."""
    old_records = _first_records(old_zone)
    new_records = _first_records(new_zone)
    changes: list[DiffChange] = []

    for key in sorted(old_records.keys() | new_records.keys()):
        old = old_records.get(key)
        new = new_records.get(key)
        if old is None:
            changes.append(DiffChange("added", key, None, new))
        elif new is None:
            changes.append(DiffChange("removed", key, old, None))
        elif old.ttl != new.ttl:
            changes.append(DiffChange("ttl", key, old, new))

    old_soa = _first_soa(old_zone)
    new_soa = _first_soa(new_zone)
    old_serial = old_soa.soa.serial if old_soa is not None and old_soa.soa is not None else None
    new_serial = new_soa.soa.serial if new_soa is not None and new_soa.soa is not None else None
    serial_transition = (
        (old_serial, new_serial)
        if old_serial is not None and new_serial is not None and old_serial != new_serial
        else None
    )
    warning_serial = (
        new_serial
        if changes and old_serial is not None and new_serial is not None and new_serial <= old_serial
        else None
    )

    return DiffResult(tuple(changes), serial_transition, warning_serial)
