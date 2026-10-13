"""运营数据分析服务。

把散落在各个报表里的聚合逻辑集中到本模块，路由层只负责参数校验与响应组装。
涵盖：KPI 总览、收入趋势、时段/星期分布、区域排行、里程利用率、
驾驶员绩效、车辆效率、支付方式、热力图、天气影响、异常预警。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..core.sqlutil import (
    as_float,
    as_int,
    datetime_bounds,
    dialect_name,
    is_peak_hour,
    period_expr,
)

WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
VEHICLE_STATUS_TEXT = {0: "停运", 1: "在营", 2: "维修"}
DRIVER_STATUS_TEXT = {0: "离职", 1: "在职", 2: "休假"}


def _bounds(start: date, end: date) -> Tuple[datetime, datetime]:
    return datetime_bounds(start, end)


def _range_filters(start: date, end: date):
    lo, hi = _bounds(start, end)
    return (
        models.OperationRecord.start_time >= lo,
        models.OperationRecord.start_time < hi,
    )


# --------------------------------------------------------------------------
# KPI 总览
# --------------------------------------------------------------------------


def kpi_overview(db: Session, start: date, end: date) -> Dict[str, Any]:
    """运营核心 KPI，并给出与上一等长周期的环比。"""
    current = _period_kpi(db, start, end)
    span = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    previous = _period_kpi(db, prev_start, prev_end)

    def change(key: str) -> Optional[float]:
        now, before = current.get(key), previous.get(key)
        if not before:
            return None
        return round((now - before) / before * 100, 2)

    current["vs_prev"] = {
        key: change(key)
        for key in ("order_count", "income", "empty_rate", "fulfil_rate", "avg_amount", "request_count")
    }
    current["prev_period"] = {"start": prev_start.isoformat(), "end": prev_end.isoformat()}
    current["span_days"] = span
    return current


def _period_kpi(db: Session, start: date, end: date) -> Dict[str, Any]:
    lo, hi = _bounds(start, end)

    row = (
        db.query(
            func.count(models.OperationRecord.id),
            func.coalesce(func.sum(models.OperationRecord.amount), 0),
            func.coalesce(func.sum(models.OperationRecord.loaded_mileage), 0),
            func.coalesce(func.sum(models.OperationRecord.empty_mileage), 0),
            func.coalesce(func.avg(models.OperationRecord.amount), 0),
            func.coalesce(func.avg(models.OperationRecord.loaded_mileage), 0),
            func.coalesce(func.avg(models.OperationRecord.duration_minutes), 0),
            func.count(func.distinct(models.OperationRecord.vehicle_id)),
            func.count(func.distinct(models.OperationRecord.driver_id)),
        )
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .first()
    )
    order_count = as_int(row[0])
    income = as_float(row[1])
    loaded = as_float(row[2])
    empty = as_float(row[3])

    req_row = (
        db.query(
            func.count(models.RideRequest.id),
            func.sum(case((models.RideRequest.status == 2, 1), else_=0)),
            func.coalesce(func.avg(models.RideRequest.wait_seconds), 0),
        )
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi)
        .first()
    )
    request_count = as_int(req_row[0])
    fulfilled = as_int(req_row[1])

    peak_row = (
        db.query(func.coalesce(func.sum(models.OperationRecord.amount), 0))
        .filter(
            models.OperationRecord.start_time >= lo,
            models.OperationRecord.start_time < hi,
            models.OperationRecord.is_peak.is_(True),
        )
        .scalar()
    )

    total_mileage = loaded + empty
    active_vehicles = as_int(row[7])
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "order_count": order_count,
        "income": round(income, 2),
        "loaded_mileage": round(loaded, 2),
        "empty_mileage": round(empty, 2),
        "total_mileage": round(total_mileage, 2),
        "empty_rate": round(empty / total_mileage * 100, 2) if total_mileage else 0.0,
        "avg_amount": round(as_float(row[4]), 2),
        "avg_distance": round(as_float(row[5]), 2),
        "avg_duration": round(as_float(row[6]), 2),
        "active_vehicles": active_vehicles,
        "active_drivers": as_int(row[8]),
        "income_per_vehicle": round(income / active_vehicles, 2) if active_vehicles else 0.0,
        "orders_per_vehicle": round(order_count / active_vehicles, 2) if active_vehicles else 0.0,
        "request_count": request_count,
        "fulfilled_count": fulfilled,
        "fulfil_rate": round(fulfilled / request_count * 100, 2) if request_count else 0.0,
        "avg_wait_seconds": round(as_float(req_row[2]), 1),
        "peak_income": round(as_float(peak_row), 2),
        "peak_income_ratio": round(as_float(peak_row) / income * 100, 2) if income else 0.0,
    }


# --------------------------------------------------------------------------
# 趋势与分布
# --------------------------------------------------------------------------


def income_trend(
    db: Session, start: date, end: date, group_by: str = "day"
) -> List[Dict[str, Any]]:
    """按日/周/月的收入与订单量趋势。"""
    lo, hi = _bounds(start, end)
    if group_by not in ("hour", "day", "week", "month"):
        group_by = "day"
    label = period_expr(db, models.OperationRecord.start_time, group_by)
    rows = (
        db.query(
            label.label("period"),
            func.count(models.OperationRecord.id),
            func.coalesce(func.sum(models.OperationRecord.amount), 0),
            func.coalesce(func.sum(models.OperationRecord.loaded_mileage), 0),
            func.coalesce(func.sum(models.OperationRecord.empty_mileage), 0),
        )
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(label)
        .order_by(label)
        .all()
    )
    output = []
    for period, count, amount, loaded, empty in rows:
        total = as_float(loaded) + as_float(empty)
        output.append(
            {
                "period": str(period),
                "order_count": as_int(count),
                "income": round(as_float(amount), 2),
                "avg_amount": round(as_float(amount) / count, 2) if count else 0.0,
                "empty_rate": round(as_float(empty) / total * 100, 2) if total else 0.0,
            }
        )
    return output


def hourly_profile(db: Session, start: date, end: date) -> List[Dict[str, Any]]:
    """24 小时需求—供给分布（需求=叫车请求，供给=完成订单）。"""
    lo, hi = _bounds(start, end)
    demand_rows = dict(
        db.query(models.RideRequest.hour, func.count(models.RideRequest.id))
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi)
        .group_by(models.RideRequest.hour)
        .all()
    )
    supply_rows = dict(
        db.query(models.OperationRecord.hour, func.count(models.OperationRecord.id))
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.OperationRecord.hour)
        .all()
    )
    income_rows = dict(
        db.query(models.OperationRecord.hour, func.coalesce(func.sum(models.OperationRecord.amount), 0))
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.OperationRecord.hour)
        .all()
    )
    output = []
    for hour in range(24):
        demand = as_int(demand_rows.get(hour))
        supply = as_int(supply_rows.get(hour))
        output.append(
            {
                "hour": hour,
                "hour_label": f"{hour:02d}:00",
                "demand": demand,
                "supply": supply,
                "income": round(as_float(income_rows.get(hour)), 2),
                "unfulfilled": max(0, demand - supply),
                "fulfil_rate": round(supply / demand * 100, 2) if demand else 0.0,
                "is_peak": is_peak_hour(hour, settings.PEAK_HOURS),
            }
        )
    return output


def weekday_profile(db: Session, start: date, end: date) -> List[Dict[str, Any]]:
    """周一至周日的需求与完成情况。"""
    lo, hi = _bounds(start, end)
    demand = dict(
        db.query(models.RideRequest.weekday, func.count(models.RideRequest.id))
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi)
        .group_by(models.RideRequest.weekday)
        .all()
    )
    supply = dict(
        db.query(models.OperationRecord.weekday, func.count(models.OperationRecord.id))
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.OperationRecord.weekday)
        .all()
    )
    income = dict(
        db.query(models.OperationRecord.weekday, func.coalesce(func.sum(models.OperationRecord.amount), 0))
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.OperationRecord.weekday)
        .all()
    )
    days = max(1, (end - start).days + 1)
    output = []
    for weekday in range(7):
        d = as_int(demand.get(weekday))
        s = as_int(supply.get(weekday))
        output.append(
            {
                "weekday": weekday,
                "weekday_label": WEEKDAY_NAMES[weekday],
                "demand": d,
                "supply": s,
                "income": round(as_float(income.get(weekday)), 2),
                "is_weekend": weekday >= 5,
            }
        )
    return output


def heatmap(db: Session, start: date, end: date) -> Dict[str, Any]:
    """「星期 × 小时」需求热力图数据。"""
    lo, hi = _bounds(start, end)
    rows = (
        db.query(
            models.RideRequest.weekday,
            models.RideRequest.hour,
            func.count(models.RideRequest.id),
        )
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi)
        .group_by(models.RideRequest.weekday, models.RideRequest.hour)
        .all()
    )
    matrix = [[0 for _ in range(24)] for _ in range(7)]
    for weekday, hour, count in rows:
        matrix[int(weekday)][int(hour)] = as_int(count)
    # 折算为「日均单量」，便于跨时段比较
    weeks = max(1.0, ((end - start).days + 1) / 7.0)
    averaged = [[round(value / weeks, 2) for value in row] for row in matrix]
    flat = [value for row in averaged for value in row]
    return {
        "x_labels": [f"{h:02d}" for h in range(24)],
        "y_labels": list(WEEKDAY_NAMES),
        "data": [[x, y, averaged[y][x]] for y in range(7) for x in range(24)],
        "matrix": averaged,
        "max_value": max(flat) if flat else 0,
        "min_value": min(flat) if flat else 0,
    }


# --------------------------------------------------------------------------
# 排行与效率
# --------------------------------------------------------------------------


def region_ranking(db: Session, start: date, end: date) -> List[Dict[str, Any]]:
    """区域热度排行：需求、完成、收入、未满足率、空驶率。"""
    lo, hi = _bounds(start, end)
    demand_rows = dict(
        db.query(models.RideRequest.region_id, func.count(models.RideRequest.id))
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi)
        .group_by(models.RideRequest.region_id)
        .all()
    )
    unfulfilled_rows = dict(
        db.query(models.RideRequest.region_id, func.count(models.RideRequest.id))
        .filter(
            models.RideRequest.request_time >= lo,
            models.RideRequest.request_time < hi,
            models.RideRequest.status.in_((0, 3)),
        )
        .group_by(models.RideRequest.region_id)
        .all()
    )
    op_rows = {
        region_id: (as_int(count), as_float(amount), as_float(loaded), as_float(empty))
        for region_id, count, amount, loaded, empty in db.query(
            models.OperationRecord.pickup_region_id,
            func.count(models.OperationRecord.id),
            func.coalesce(func.sum(models.OperationRecord.amount), 0),
            func.coalesce(func.sum(models.OperationRecord.loaded_mileage), 0),
            func.coalesce(func.sum(models.OperationRecord.empty_mileage), 0),
        )
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.OperationRecord.pickup_region_id)
        .all()
    }
    regions = {r.id: r for r in db.query(models.Region).all()}

    output = []
    for region_id, region in regions.items():
        demand = as_int(demand_rows.get(region_id))
        unfulfilled = as_int(unfulfilled_rows.get(region_id))
        count, amount, loaded, empty = op_rows.get(region_id, (0, 0.0, 0.0, 0.0))
        total = loaded + empty
        output.append(
            {
                "region_id": region_id,
                "region_name": region.name,
                "region_type": region.region_type,
                "demand_level": region.demand_level,
                "demand": demand,
                "order_count": count,
                "income": round(amount, 2),
                "unfulfilled": unfulfilled,
                "unfulfil_rate": round(unfulfilled / demand * 100, 2) if demand else 0.0,
                "empty_rate": round(empty / total * 100, 2) if total else 0.0,
                "avg_amount": round(amount / count, 2) if count else 0.0,
            }
        )
    output.sort(key=lambda item: item["income"], reverse=True)
    return output


def load_rate(
    db: Session,
    start: date,
    end: date,
    vehicle_id: Optional[int] = None,
    region_id: Optional[int] = None,
) -> Dict[str, Any]:
    """里程利用率（载客里程 / 总里程）及空驶情况。"""
    lo, hi = _bounds(start, end)
    query = db.query(
        func.coalesce(func.sum(models.OperationRecord.loaded_mileage), 0),
        func.coalesce(func.sum(models.OperationRecord.empty_mileage), 0),
        func.count(models.OperationRecord.id),
    ).filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
    if vehicle_id:
        query = query.filter(models.OperationRecord.vehicle_id == vehicle_id)
    if region_id:
        query = query.filter(models.OperationRecord.pickup_region_id == region_id)
    loaded, empty, count = query.first()
    loaded, empty = as_float(loaded), as_float(empty)
    total = loaded + empty
    return {
        "loaded_mileage": round(loaded, 2),
        "empty_mileage": round(empty, 2),
        "total_mileage": round(total, 2),
        "load_rate": round(loaded / total * 100, 2) if total else 0.0,
        "empty_rate": round(empty / total * 100, 2) if total else 0.0,
        "order_count": as_int(count),
    }


def driver_ranking(
    db: Session, start: date, end: date, top_n: int = 10, sort_by: str = "income"
) -> List[Dict[str, Any]]:
    """驾驶员绩效排行。"""
    lo, hi = _bounds(start, end)
    rows = (
        db.query(
            models.Driver.id,
            models.Driver.name,
            models.Driver.rating,
            models.Driver.status,
            func.count(models.OperationRecord.id).label("order_count"),
            func.coalesce(func.sum(models.OperationRecord.amount), 0).label("income"),
            func.coalesce(func.sum(models.OperationRecord.loaded_mileage), 0).label("loaded"),
            func.coalesce(func.sum(models.OperationRecord.empty_mileage), 0).label("empty"),
            func.coalesce(func.avg(models.OperationRecord.amount), 0).label("avg_amount"),
        )
        .join(models.OperationRecord, models.OperationRecord.driver_id == models.Driver.id)
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.Driver.id)
        .all()
    )
    output = []
    for driver_id, name, rating, status, count, income, loaded, empty, avg_amount in rows:
        total = as_float(loaded) + as_float(empty)
        output.append(
            {
                "driver_id": driver_id,
                "name": name,
                "rating": as_float(rating, 5.0),
                "status": as_int(status, 1),
                "order_count": as_int(count),
                "income": round(as_float(income), 2),
                "loaded_mileage": round(as_float(loaded), 2),
                "empty_rate": round(as_float(empty) / total * 100, 2) if total else 0.0,
                "avg_amount": round(as_float(avg_amount), 2),
                # 综合绩效分：收入 60% + 单量 25% + 评分 15%（归一化后加权）
                "score": 0.0,
            }
        )
    if output:
        max_income = max(item["income"] for item in output) or 1
        max_orders = max(item["order_count"] for item in output) or 1
        for item in output:
            item["score"] = round(
                item["income"] / max_income * 60
                + item["order_count"] / max_orders * 25
                + item["rating"] / 5.0 * 15,
                2,
            )
    key_map = {"income": "income", "order_count": "order_count", "score": "score", "rating": "rating"}
    output.sort(key=lambda item: item[key_map.get(sort_by, "income")], reverse=True)
    return output[: max(1, top_n)]


def vehicle_efficiency(
    db: Session, start: date, end: date, top_n: int = 10, order: str = "desc"
) -> List[Dict[str, Any]]:
    """车辆运营效率排行。"""
    lo, hi = _bounds(start, end)
    rows = (
        db.query(
            models.Vehicle.id,
            models.Vehicle.plate_number,
            models.Vehicle.brand_model,
            models.Vehicle.status,
            func.count(models.OperationRecord.id).label("order_count"),
            func.coalesce(func.sum(models.OperationRecord.amount), 0).label("income"),
            func.coalesce(func.sum(models.OperationRecord.loaded_mileage), 0).label("loaded"),
            func.coalesce(func.sum(models.OperationRecord.empty_mileage), 0).label("empty"),
        )
        .join(models.OperationRecord, models.OperationRecord.vehicle_id == models.Vehicle.id)
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.Vehicle.id)
        .all()
    )
    output = []
    for vehicle_id, plate, brand, status, count, income, loaded, empty in rows:
        total = as_float(loaded) + as_float(empty)
        income_value = as_float(income)
        output.append(
            {
                "vehicle_id": vehicle_id,
                "plate_number": plate,
                "brand_model": brand,
                "status": as_int(status, 1),
                "status_text": VEHICLE_STATUS_TEXT.get(as_int(status, 1), "未知"),
                "order_count": as_int(count),
                "income": round(income_value, 2),
                "total_mileage": round(total, 2),
                "empty_rate": round(as_float(empty) / total * 100, 2) if total else 0.0,
                "income_per_km": round(income_value / total, 2) if total else 0.0,
            }
        )
    output.sort(key=lambda item: item["income"], reverse=order != "asc")
    return output[: max(1, top_n)]


def pay_type_distribution(db: Session, start: date, end: date) -> List[Dict[str, Any]]:
    """支付方式占比。"""
    lo, hi = _bounds(start, end)
    rows = (
        db.query(
            models.OperationRecord.pay_type,
            func.count(models.OperationRecord.id),
            func.coalesce(func.sum(models.OperationRecord.amount), 0),
        )
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.OperationRecord.pay_type)
        .all()
    )
    total = sum(as_int(r[1]) for r in rows) or 1
    output = [
        {
            "pay_type": pay_type or "未填写",
            "order_count": as_int(count),
            "income": round(as_float(amount), 2),
            "ratio": round(as_int(count) / total * 100, 2),
        }
        for pay_type, count, amount in rows
    ]
    output.sort(key=lambda item: item["order_count"], reverse=True)
    return output


def weather_impact(db: Session, start: date, end: date) -> List[Dict[str, Any]]:
    """天气对需求与运力的影响。"""
    lo, hi = _bounds(start, end)
    demand = dict(
        db.query(models.RideRequest.weather, func.count(models.RideRequest.id))
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi)
        .group_by(models.RideRequest.weather)
        .all()
    )
    supply = dict(
        db.query(models.OperationRecord.weather, func.count(models.OperationRecord.id))
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.OperationRecord.weather)
        .all()
    )
    income = dict(
        db.query(
            models.OperationRecord.weather,
            func.coalesce(func.sum(models.OperationRecord.amount), 0),
        )
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.OperationRecord.weather)
        .all()
    )
    output = []
    for weather in sorted(set(demand) | set(supply)):
        d = as_int(demand.get(weather))
        s = as_int(supply.get(weather))
        output.append(
            {
                "weather": weather or "未知",
                "demand": d,
                "supply": s,
                "income": round(as_float(income.get(weather)), 2),
                "avg_amount": round(as_float(income.get(weather)) / s, 2) if s else 0.0,
                "fulfil_rate": round(s / d * 100, 2) if d else 0.0,
            }
        )
    output.sort(key=lambda item: item["demand"], reverse=True)
    return output


def region_compare(db: Session, start: date, end: date, region_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """区域多指标对比（雷达图数据）。"""
    ranking = region_ranking(db, start, end)
    if region_ids:
        ranking = [item for item in ranking if item["region_id"] in region_ids]
    if not ranking:
        return {"indicators": [], "series": []}
    metrics = [
        ("income", "总收入"),
        ("order_count", "订单量"),
        ("demand", "需求量"),
        ("avg_amount", "单均收入"),
    ]
    maxima = {
        key: max((item[key] for item in ranking), default=0) or 1 for key, _ in metrics
    }
    indicators = [{"name": label, "max": 100} for _, label in metrics]
    series = []
    for item in ranking[:6]:
        series.append(
            {
                "name": item["region_name"],
                "value": [round(item[key] / maxima[key] * 100, 2) for key, _ in metrics],
                "raw": {key: item[key] for key, _ in metrics},
            }
        )
    return {"indicators": indicators, "series": series}


# --------------------------------------------------------------------------
# 异常预警
# --------------------------------------------------------------------------


def abnormal_alerts(db: Session, days: int = 7) -> List[Dict[str, Any]]:
    """汇总各类运营异常与到期提醒。"""
    alerts: List[Dict[str, Any]] = []
    today = date.today()
    end = today
    start = today - timedelta(days=days - 1)
    lo, hi = _bounds(start, end)

    # 1) 区域未满足率过高
    region_rank = region_ranking(db, start, end)
    for item in region_rank:
        if item["demand"] >= 50 and item["unfulfil_rate"] >= settings.UNFULFILLED_RATE_WARN * 100:
            alerts.append(
                {
                    "level": "high" if item["unfulfil_rate"] >= 30 else "medium",
                    "type": "需求未满足",
                    "target": item["region_name"],
                    "title": f"{item['region_name']} 叫车未满足率 {item['unfulfil_rate']}%",
                    "content": (
                        f"近 {days} 天该区域共 {item['demand']} 单叫车需求，"
                        f"其中 {item['unfulfilled']} 单未被满足，运力明显不足。"
                    ),
                    "value": item["unfulfil_rate"],
                    "unit": "%",
                    "suggestion": "建议在高峰时段向该区域调度运力，或增加该区域排班车辆。",
                }
            )

    # 2) 车辆空驶率异常
    rows = (
        db.query(
            models.Vehicle.plate_number,
            func.coalesce(func.sum(models.OperationRecord.empty_mileage), 0),
            func.coalesce(func.sum(models.OperationRecord.loaded_mileage), 0),
            func.count(models.OperationRecord.id),
        )
        .join(models.OperationRecord, models.OperationRecord.vehicle_id == models.Vehicle.id)
        .filter(models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi)
        .group_by(models.Vehicle.id)
        .all()
    )
    for plate, empty, loaded, count in rows:
        total = as_float(empty) + as_float(loaded)
        if total <= 0 or count < 10:
            continue
        rate = as_float(empty) / total
        if rate > settings.EMPTY_RATE_WARN:
            alerts.append(
                {
                    "level": "medium",
                    "type": "空驶率偏高",
                    "target": plate,
                    "title": f"车辆 {plate} 空驶率 {rate * 100:.1f}%",
                    "content": f"近 {days} 天该车完成 {count} 单，空驶里程占比超过 {settings.EMPTY_RATE_WARN * 100:.0f}% 的预警线。",
                    "value": round(rate * 100, 2),
                    "unit": "%",
                    "suggestion": "建议优化接单区域与巡游路线，减少空驶。",
                }
            )

    # 3) 收入环比下滑
    span = days
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    now_kpi = _period_kpi(db, start, end)
    prev_kpi = _period_kpi(db, prev_start, prev_end)
    if prev_kpi["income"] > 0:
        change = (now_kpi["income"] - prev_kpi["income"]) / prev_kpi["income"]
        if change < settings.INCOME_DROP_WARN:
            alerts.append(
                {
                    "level": "high",
                    "type": "收入下滑",
                    "target": "全公司",
                    "title": f"总收入环比下降 {abs(change) * 100:.1f}%",
                    "content": (
                        f"近 {days} 天收入 {now_kpi['income']:.0f} 元，"
                        f"上一周期 {prev_kpi['income']:.0f} 元。"
                    ),
                    "value": round(change * 100, 2),
                    "unit": "%",
                    "suggestion": "建议结合时段与区域需求分析，调整运力投放与排班结构。",
                }
            )

    # 4) 保险 / 营运证 / 保养到期
    deadline = today + timedelta(days=settings.INSURANCE_WARN_DAYS)
    vehicles = db.query(models.Vehicle).filter(models.Vehicle.status != 0).all()
    for vehicle in vehicles:
        for attr, label, warn_days in (
            ("insurance_expire", "保险", settings.INSURANCE_WARN_DAYS),
            ("cert_expire", "营运证", settings.CERT_WARN_DAYS),
            ("next_maintenance_date", "保养", settings.MAINTENANCE_WARN_DAYS),
        ):
            value = getattr(vehicle, attr)
            if not value:
                continue
            limit = today + timedelta(days=warn_days)
            if value <= limit:
                overdue = value < today
                alerts.append(
                    {
                        "level": "high" if overdue else "medium",
                        "type": f"{label}到期",
                        "target": vehicle.plate_number,
                        "title": f"车辆 {vehicle.plate_number} {label}{'已过期' if overdue else '即将到期'}",
                        "content": f"{label}日期：{value.isoformat()}",
                        "value": (value - today).days,
                        "unit": "天",
                        "suggestion": f"请尽快办理{label}相关手续。" if overdue else f"请在 {value.isoformat()} 前完成{label}办理。",
                    }
                )

    # 5) 驾驶证到期
    limit = today + timedelta(days=settings.LICENSE_WARN_DAYS)
    for driver in db.query(models.Driver).filter(models.Driver.status == 1).all():
        if driver.license_expire and driver.license_expire <= limit:
            overdue = driver.license_expire < today
            alerts.append(
                {
                    "level": "high" if overdue else "medium",
                    "type": "驾驶证到期",
                    "target": driver.name,
                    "title": f"驾驶员 {driver.name} 驾驶证{'已过期' if overdue else '即将到期'}",
                    "content": f"驾驶证有效期至：{driver.license_expire.isoformat()}",
                    "value": (driver.license_expire - today).days,
                    "unit": "天",
                    "suggestion": "请提醒驾驶员及时换证，避免影响营运资质。",
                }
            )

    # 6) 长时间未营运的在营车辆
    active_ids = {
        row[0]
        for row in db.query(models.OperationRecord.vehicle_id)
        .filter(models.OperationRecord.start_time >= lo)
        .distinct()
        .all()
    }
    idle = (
        db.query(models.Vehicle)
        .filter(models.Vehicle.status == 1)
        .all()
    )
    idle_list = [v for v in idle if v.id not in active_ids]
    if idle_list:
        alerts.append(
            {
                "level": "low" if len(idle_list) < 5 else "medium",
                "type": "车辆闲置",
                "target": "在营车辆",
                "title": f"{len(idle_list)} 台在营车辆近 {days} 天无营运记录",
                "content": "、".join(v.plate_number for v in idle_list[:8])
                + ("..." if len(idle_list) > 8 else ""),
                "value": len(idle_list),
                "unit": "台",
                "suggestion": "请核实车辆是否实际停运，必要时调整车辆状态或安排上线。",
            }
        )

    order = {"high": 0, "medium": 1, "low": 2}
    alerts.sort(key=lambda item: (order.get(item["level"], 3), -abs(as_float(item.get("value")))))
    return alerts
