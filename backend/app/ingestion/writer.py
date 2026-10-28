from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, literal_column, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Base, SourceCorrection

CHUNK = 1000


@dataclass
class UpsertCounts:
    inserted: int = 0
    updated: int = 0

    def __iadd__(self, other: "UpsertCounts") -> "UpsertCounts":
        self.inserted += other.inserted
        self.updated += other.updated
        return self


Row = dict[str, Any]


def _chunks(rows: Sequence[Row], size: int = CHUNK) -> Iterable[Sequence[Row]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def upsert(
    session: Session,
    model: type[Base],
    rows: Sequence[dict[str, Any]],
    key: Sequence[str],
    *,
    provenance: dict[str, Any] | None = None,
    compare_exclude: frozenset[str] = frozenset(),
) -> UpsertCounts:
    """INSERT … ON CONFLICT DO UPDATE that only touches rows whose values actually changed.

    Only columns present in the rows are written, so writers that own different columns of the same
    table (schedule vs. game logs) do not erase each other's values. Columns in compare_exclude are
    written only when some other column changed.
    """
    counts = UpsertCounts()
    if not rows:
        return counts
    table = model.__table__
    data_cols = [c for c in rows[0] if c not in key]
    compared = [c for c in data_cols if c not in compare_exclude]
    for chunk in _chunks(rows):
        values = [{**row, **(provenance or {})} for row in chunk]
        stmt = insert(table).values(values)
        set_ = {c: stmt.excluded[c] for c in data_cols}
        if provenance:
            set_.update({c: stmt.excluded[c] for c in provenance})
            set_["updated_at"] = func.now()
        if compared:
            changed = tuple_(*[table.c[c] for c in compared]).is_distinct_from(
                tuple_(*[stmt.excluded[c] for c in compared])
            )
            stmt = stmt.on_conflict_do_update(index_elements=list(key), set_=set_, where=changed)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=list(key))
        result = session.execute(stmt.returning(literal_column("(xmax = 0)").label("inserted")))
        for (was_insert,) in result:
            if was_insert:
                counts.inserted += 1
            else:
                counts.updated += 1
    return counts


def detect_corrections(
    session: Session,
    model: type[Base],
    rows: Sequence[dict[str, Any]],
    key: Sequence[str],
    columns: Sequence[str],
    run_id: int,
) -> list[SourceCorrection]:
    """Records each stored, non-null value that the incoming rows change.

    Filling a previously empty value (e.g. a score after the game ends) is not a correction.
    """
    if not rows:
        return []
    table = model.__table__
    corrections: list[SourceCorrection] = []
    incoming = {tuple(r[k] for k in key): r for r in rows}
    key_cols = tuple_(*[table.c[k] for k in key])
    keys = list(incoming)
    for i in range(0, len(keys), CHUNK):
        stmt = select(*[table.c[k] for k in key], *[table.c[c] for c in columns]).where(
            key_cols.in_(keys[i : i + CHUNK])
        )
        for stored in session.execute(stmt).mappings():
            k = tuple(stored[c] for c in key)
            new = incoming[k]
            for col in columns:
                if col in new and stored[col] is not None and new[col] != stored[col]:
                    corrections.append(SourceCorrection(
                        ingestion_run_id=run_id,
                        table_name=table.name,
                        record_key={c: stored[c] for c in key},
                        column_name=col,
                        old_value=None if stored[col] is None else str(stored[col]),
                        new_value=None if new[col] is None else str(new[col]),
                    ))  # fmt: skip
    session.add_all(corrections)
    return corrections


def provenance(run_id: int, endpoint: str) -> dict[str, Any]:
    return {"ingestion_run_id": run_id, "source_endpoint": endpoint}
