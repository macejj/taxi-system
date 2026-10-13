"""SQL 方言适配与通用查询工具。"""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement


def dialect_name(db: Session) -> str:
    try:
        return db.get_bind().dialect.name
    except Exception:  # pragma: no cover - 兜底
        return "mysql"


def period_expr(db: Session, column, group_by: str) -> ColumnElement:
    """按 MySQL / SQLite 方言生成日期截断表达式。

    group_by 取值：hour / day / week / month。
    """
    name = dialect_name(db)
    fmt_map = {
        "hour": "%Y-%m-%d %H:00",
        "day": "%Y-%m-%d",
        "week": "%Y-%W",
        "month": "%Y-%m",
    }
    fmt = fmt_map.get(group_by, "%Y-%m-%d")
    if name == "sqlite":
        return func.strftime(fmt, column)
    return func.date_format(column, fmt)


def parse_date(value, default: Optional[date] = None) -> Optional[date]:
    """把 'YYYY-MM-DD' 字符串解析为 date。"""
    if value in (None, ""):
        return default
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def date_range(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    default_days: int = 7,
) -> tuple[date, date]:
    """归一化查询区间，end 为闭区间日期。"""
    today = date.today()
    end = parse_date(end_date, today)
    start = parse_date(start_date, end - timedelta(days=default_days - 1))
    if start > end:
        start, end = end, start
    return start, end


def datetime_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """把日期闭区间转换为 [起, 止) 的 datetime 边界。"""
    return (
        datetime.combine(start, datetime.min.time()),
        datetime.combine(end + timedelta(days=1), datetime.min.time()),
    )


def is_peak_hour(hour: int, peak_hours) -> bool:
    for start, end in peak_hours:
        if start <= hour < end:
            return True
    return False


def as_float(value, default: float = 0.0) -> float:
    """把 Decimal / None 安全转换为 float。"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
