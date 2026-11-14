"""Timezone and date range resolution utilities for Indian retail accounting."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

KOLKATA_TZ = ZoneInfo("Asia/Kolkata")


def resolve_date_window(
    period: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    tz_name: str = "Asia/Kolkata",
) -> tuple[datetime | None, datetime | None, str]:
    """Resolve period preset or custom dates to UTC bounds and human-readable label.

    Returns:
        (start_utc, end_utc, label)
    """
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)

    if period:
        p_upper = period.upper()
        if p_upper == "TODAY":
            start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_local.astimezone(UTC), end_local.astimezone(UTC), "TODAY"

        elif p_upper == "YESTERDAY":
            yesterday_local = now_local - timedelta(days=1)
            start_local = yesterday_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end_local = yesterday_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_local.astimezone(UTC), end_local.astimezone(UTC), "YESTERDAY"

        elif p_upper == "LAST_7_DAYS":
            start_local = (now_local - timedelta(days=6)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_local.astimezone(UTC), end_local.astimezone(UTC), "LAST_7_DAYS"

        elif p_upper == "LAST_30_DAYS":
            start_local = (now_local - timedelta(days=29)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_local.astimezone(UTC), end_local.astimezone(UTC), "LAST_30_DAYS"

        elif p_upper == "THIS_MONTH":
            start_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_local.astimezone(UTC), end_local.astimezone(UTC), "THIS_MONTH"

        elif p_upper == "ALL_TIME":
            return None, None, "ALL_TIME"

    # Custom or fallback
    if start_date or end_date:
        s_utc = (
            start_date.replace(tzinfo=UTC)
            if start_date and start_date.tzinfo is None
            else start_date
        )
        e_utc = end_date.replace(tzinfo=UTC) if end_date and end_date.tzinfo is None else end_date
        return s_utc, e_utc, "CUSTOM"

    return None, None, "ALL_TIME"


def to_kolkata_date_str(dt: datetime) -> str:
    """Format UTC datetime into YYYY-MM-DD in Asia/Kolkata timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    local_dt = dt.astimezone(KOLKATA_TZ)
    return local_dt.strftime("%Y-%m-%d")
