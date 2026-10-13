"""叫车需求（需求侧）数据接口。"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.deps import PageParams, get_current_user, paginate
from ..core.sqlutil import as_float, as_int, date_range, datetime_bounds
from ..database import get_db
from ..services.analytics import WEEKDAY_NAMES

router = APIRouter()

STATUS_TEXT = {0: "无人接单", 1: "已接单", 2: "已完成", 3: "已取消"}


def enrich_requests(db: Session, rows: List[models.RideRequest]) -> List[dict]:
    region_map = {r.id: r.name for r in db.query(models.Region).all()}
    output = []
    for row in rows:
        item = schemas.RideRequestOut.model_validate(row).model_dump()
        item["region_name"] = region_map.get(row.region_id)
        item["status_text"] = STATUS_TEXT.get(row.status, "未知")
        output.append(item)
    return output


@router.get("/", response_model=schemas.Page[schemas.RideRequestOut], summary="叫车请求分页列表")
def list_requests(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    region_id: Optional[int] = None,
    status: Optional[int] = None,
    hour: Optional[int] = Query(None, ge=0, le=23),
    weather: Optional[str] = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.RideRequest)
    if start_date or end_date:
        start, end = date_range(start_date, end_date, default_days=7)
        lo, hi = datetime_bounds(start, end)
        query = query.filter(
            models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi
        )
    if region_id:
        query = query.filter(models.RideRequest.region_id == region_id)
    if status is not None:
        query = query.filter(models.RideRequest.status == status)
    if hour is not None:
        query = query.filter(models.RideRequest.hour == hour)
    if weather:
        query = query.filter(models.RideRequest.weather == weather)
    query = query.order_by(models.RideRequest.request_time.desc())
    result = paginate(query, page)
    result["items"] = enrich_requests(db, result["items"])
    return result


@router.get("/summary", summary="需求汇总统计")
def demand_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=7)
    lo, hi = datetime_bounds(start, end)
    query = db.query(
        func.count(models.RideRequest.id),
        func.sum(case((models.RideRequest.status == 2, 1), else_=0)),
        func.sum(case((models.RideRequest.status.in_((0, 3)), 1), else_=0)),
        func.coalesce(func.avg(models.RideRequest.wait_seconds), 0),
        func.coalesce(func.sum(models.RideRequest.passenger_count), 0),
    ).filter(
        models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi
    )
    if region_id:
        query = query.filter(models.RideRequest.region_id == region_id)
    total, fulfilled, unfulfilled, avg_wait, passengers = query.first()
    total = as_int(total)
    fulfilled = as_int(fulfilled)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "request_count": total,
        "fulfilled_count": fulfilled,
        "unfulfilled_count": as_int(unfulfilled),
        "fulfil_rate": round(fulfilled / total * 100, 2) if total else 0.0,
        "avg_wait_seconds": round(as_float(avg_wait), 1),
        "passenger_count": as_int(passengers),
        "avg_daily": round(total / max(1, (end - start).days + 1), 1),
    }


@router.get("/region-hour-matrix", summary="区域 × 小时需求矩阵（供调度参考）")
def region_hour_matrix(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=14)
    lo, hi = datetime_bounds(start, end)
    rows = (
        db.query(
            models.RideRequest.region_id,
            models.RideRequest.hour,
            func.count(models.RideRequest.id),
        )
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi)
        .group_by(models.RideRequest.region_id, models.RideRequest.hour)
        .all()
    )
    regions = {r.id: r.name for r in db.query(models.Region).order_by(models.Region.code).all()}
    days = max(1, (end - start).days + 1)
    index = {name: i for i, name in enumerate(regions.values())}
    matrix = [[0.0] * 24 for _ in regions]
    for region_id, hour, count in rows:
        name = regions.get(region_id)
        if name is None:
            continue
        matrix[index[name]][int(hour)] = round(as_int(count) / days, 2)
    return {
        "y_labels": list(regions.values()),
        "x_labels": [f"{h:02d}" for h in range(24)],
        "matrix": matrix,
        "days": days,
    }


@router.get("/weekday-hour", summary="星期 × 小时需求分布")
def weekday_hour(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=28)
    lo, hi = datetime_bounds(start, end)
    query = (
        db.query(
            models.RideRequest.weekday,
            models.RideRequest.hour,
            func.count(models.RideRequest.id),
        )
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time < hi)
    )
    if region_id:
        query = query.filter(models.RideRequest.region_id == region_id)
    rows = query.group_by(models.RideRequest.weekday, models.RideRequest.hour).all()
    matrix = [[0] * 24 for _ in range(7)]
    for weekday, hour, count in rows:
        matrix[int(weekday)][int(hour)] = as_int(count)
    return {
        "x_labels": [f"{h:02d}" for h in range(24)],
        "y_labels": list(WEEKDAY_NAMES),
        "matrix": matrix,
    }


@router.post("/", response_model=schemas.RideRequestOut, summary="新增叫车请求")
def create_request(
    payload: schemas.RideRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not db.get(models.Region, payload.region_id):
        raise HTTPException(status_code=400, detail="区域不存在")
    data = payload.model_dump()
    data["request_no"] = data.get("request_no") or f"REQ{payload.request_time.strftime('%Y%m%d%H%M%S')}"
    data["stat_date"] = payload.request_time.date()
    data["hour"] = payload.request_time.hour
    data["weekday"] = payload.request_time.weekday()
    request = models.RideRequest(**data)
    db.add(request)
    db.commit()
    db.refresh(request)
    return enrich_requests(db, [request])[0]


@router.delete("/{request_id}", response_model=schemas.Message, summary="删除叫车请求")
def delete_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    request = db.get(models.RideRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail="叫车请求不存在")
    db.delete(request)
    db.commit()
    return {"message": "删除成功"}
