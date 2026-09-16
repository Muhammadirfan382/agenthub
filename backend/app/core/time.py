"""UTC helpers.

SQLite has no timezone-aware storage, so datetimes read back from it are naive.
Everything crossing the API boundary is normalised to UTC here.
"""

from datetime import UTC, datetime


def now_utc() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
