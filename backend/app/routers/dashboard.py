"""综合驾驶舱接口：一屏展示核心指标、趋势与预警。"""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..core.deps import get_current_user
from ..core.sqlutil import as_float, as_int, datetime_bounds
from ..database import get_db
from ..services import analytics

router = APIRouter()


@router.get("/summary", summary="驾驶舱总览")
def summary(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    today = date.today()
    yesterday = today - timedelta(days=1)

    today_kpi = analytics._period_kpi(db, today, today)
    yesterday_kpi = analytics._period_kpi(db, yesterday, yesterday)
    week_kpi = analytics.kpi_overview(db, today - timedelta(days=6), today)

    def ratio(current: float, previous: float):
        if not previous:
            return None
        return round((current - previous) / previous * 100, 2)

    # 运力概况
    vehicle_status = dict(
        db.query(models.Vehicle.status, func.count(models.Vehicle.id))
        .group_by(models.Vehicle.status)
        .all()
    )
    driver_status = dict(
        db.query(models.Driver.status, func.count(models.Driver.id))
        .group_by(models.Driver.status)
        .all()
    )

    # 实时（最近 6 小时）需求与完成
    now = datetime.now()
    lo = (now - timedelta(hours=6)).replace(minute=0, second=0, microsecond=0)
    demand = (
        db.query(func.count(models.RideRequest.id))
        .filter(models.RideRequest.request_time >= lo)
        .scalar()
        or 0
    )
    supply = (
        db.query(func.count(models.OperationRecord.id))
        .filter(models.OperationRecord.start_time >= lo)
        .scalar()
        or 0
    )

    pending_dispatch = (
        db.query(func.count(models.DispatchOrder.id))
        .filter(models.DispatchOrder.status.in_((0, 1)))
        .scalar()
        or 0
    )

    return {
        "today": {
            "date": today.isoformat(),
            **today_kpi,
            "vs_yesterday": {
                "order_count": ratio(today_kpi["order_count"], yesterday_kpi["order_count"]),
                "income": ratio(today_kpi["income"], yesterday_kpi["income"]),
                "empty_rate": ratio(today_kpi["empty_rate"], yesterday_kpi["empty_rate"]),
                "fulfil_rate": ratio(today_kpi["fulfil_rate"], yesterday_kpi["fulfil_rate"]),
            },
        },
        "week": week_kpi,
        "fleet": {
            "vehicle_total": sum(as_int(v) for v in vehicle_status.values()),
            "vehicle_active": as_int(vehicle_status.get(1, 0)),
            "vehicle_idle": as_int(vehicle_status.get(0, 0)),
            "vehicle_repair": as_int(vehicle_status.get(2, 0)),
            "driver_total": sum(as_int(v) for v in driver_status.values()),
            "driver_active": as_int(driver_status.get(1, 0)),
            "driver_leave": as_int(driver_status.get(0, 0)),
            "driver_rest": as_int(driver_status.get(2, 0)),
        },
        "realtime": {
            "window_hours": 6,
            "demand": as_int(demand),
            "supply": as_int(supply),
            "fulfil_rate": round(as_int(supply) / as_int(demand) * 100, 2) if demand else 0.0,
        },
        "pending_dispatch": as_int(pending_dispatch),
        "updated_at": now,
    }


@router.get("/trend", summary="驾驶舱趋势图（近 N 天）")
def trend(
    days: int = Query(14, ge=3, le=90),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    end = date.today()
    start = end - timedelta(days=days - 1)
    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "income": analytics.income_trend(db, start, end, "day"),
        "hourly": analytics.hourly_profile(db, start, end),
        "regions": analytics.region_ranking(db, start, end)[:8],
    }


@router.get("/alerts", summary="驾驶舱预警（前 N 条）")
def alerts(
    limit: int = Query(8, ge=1, le=50),
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = analytics.abnormal_alerts(db, days)
    return {"total": len(rows), "items": rows[:limit]}


@router.get("/health", summary="系统与数据健康度")
def health(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    latest_request = db.query(func.max(models.RideRequest.request_time)).scalar()
    latest_order = db.query(func.max(models.OperationRecord.start_time)).scalar()
    counts = {
        "region": db.query(func.count(models.Region.id)).scalar() or 0,
        "vehicle": db.query(func.count(models.Vehicle.id)).scalar() or 0,
        "driver": db.query(func.count(models.Driver.id)).scalar() or 0,
        "ride_request": db.query(func.count(models.RideRequest.id)).scalar() or 0,
        "operation_record": db.query(func.count(models.OperationRecord.id)).scalar() or 0,
        "dispatch_plan": db.query(func.count(models.DispatchPlan.id)).scalar() or 0,
        "dispatch_order": db.query(func.count(models.DispatchOrder.id)).scalar() or 0,
        "forecast_result": db.query(func.count(models.ForecastResult.id)).scalar() or 0,
    }
    days_of_data = 0
    if latest_order and counts["operation_record"]:
        earliest = db.query(func.min(models.OperationRecord.start_time)).scalar()
        if earliest:
            days_of_data = (latest_order.date() - earliest.date()).days + 1
    return {
        "counts": counts,
        "latest_request_time": latest_request,
        "latest_order_time": latest_order,
        "history_days": days_of_data,
        "ready_for_forecast": counts["ride_request"] > 0 and days_of_data >= 14,
    }
