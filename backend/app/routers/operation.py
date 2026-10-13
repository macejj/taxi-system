"""营运订单（运营数据）管理接口：增删改查、Excel 导入导出。"""
import csv
import io
from datetime import date, datetime, timedelta
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..core.deps import PageParams, get_current_user, paginate
from ..core.sqlutil import as_float, as_int, date_range, datetime_bounds, is_peak_hour
from ..database import get_db

router = APIRouter()

IMPORT_COLUMNS = [
    "order_no",
    "vehicle_plate",
    "driver_name",
    "pickup_region",
    "dropoff_region",
    "start_time",
    "end_time",
    "loaded_mileage",
    "empty_mileage",
    "amount",
    "pay_type",
    "weather",
]


def derive_fields(data: dict) -> dict:
    """根据上车/下车时间与里程，派生出统计所需的冗余字段。"""
    start: datetime = data["start_time"]
    end: datetime = data["end_time"]
    if end < start:
        raise HTTPException(status_code=400, detail="下车时间不能早于上车时间")
    duration = (end - start).total_seconds() / 60.0
    distance = as_float(data.get("loaded_mileage"))
    data["stat_date"] = start.date()
    data["hour"] = start.hour
    data["weekday"] = start.weekday()
    data["is_peak"] = is_peak_hour(start.hour, settings.PEAK_HOURS)
    data["duration_minutes"] = round(duration, 2)
    data["avg_speed"] = round(distance / (duration / 60.0), 2) if duration > 0 else 0.0
    data["is_holiday"] = data.get("is_holiday", False)
    return data


def enrich_operations(db: Session, records: List[models.OperationRecord]) -> List[dict]:
    """补充车牌、驾驶员姓名、上下车区域名称。"""
    if not records:
        return []
    plate_map = {v.id: v.plate_number for v in db.query(models.Vehicle).all()}
    driver_map = {d.id: d.name for d in db.query(models.Driver).all()}
    region_map = {r.id: r.name for r in db.query(models.Region).all()}
    output = []
    for record in records:
        item = schemas.OperationRecordOut.model_validate(record).model_dump()
        item["plate_number"] = plate_map.get(record.vehicle_id)
        item["driver_name"] = driver_map.get(record.driver_id)
        item["pickup_region_name"] = region_map.get(record.pickup_region_id)
        item["dropoff_region_name"] = region_map.get(record.dropoff_region_id)
        output.append(item)
    return output


def _filtered_query(
    db: Session,
    start_date: Optional[str],
    end_date: Optional[str],
    vehicle_id: Optional[int],
    driver_id: Optional[int],
    region_id: Optional[int],
    keyword: Optional[str],
    pay_type: Optional[str],
    peak: Optional[int],
    min_amount: Optional[float],
    max_amount: Optional[float],
):
    query = db.query(models.OperationRecord)
    if start_date or end_date:
        start, end = date_range(start_date, end_date, default_days=30)
        lo, hi = datetime_bounds(start, end)
        query = query.filter(
            models.OperationRecord.start_time >= lo, models.OperationRecord.start_time < hi
        )
    if vehicle_id:
        query = query.filter(models.OperationRecord.vehicle_id == vehicle_id)
    if driver_id:
        query = query.filter(models.OperationRecord.driver_id == driver_id)
    if region_id:
        query = query.filter(models.OperationRecord.pickup_region_id == region_id)
    if pay_type:
        query = query.filter(models.OperationRecord.pay_type == pay_type)
    if peak is not None:
        query = query.filter(models.OperationRecord.is_peak.is_(bool(peak)))
    if min_amount is not None:
        query = query.filter(models.OperationRecord.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(models.OperationRecord.amount <= max_amount)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(models.OperationRecord.order_no.like(like))
    return query


@router.get("/", response_model=schemas.Page[schemas.OperationRecordOut], summary="营运订单分页列表")
def list_operations(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    driver_id: Optional[int] = None,
    region_id: Optional[int] = None,
    keyword: Optional[str] = None,
    pay_type: Optional[str] = None,
    peak: Optional[int] = Query(None, description="1 仅高峰 0 仅平峰"),
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = _filtered_query(
        db, start_date, end_date, vehicle_id, driver_id, region_id, keyword,
        pay_type, peak, min_amount, max_amount,
    ).order_by(models.OperationRecord.start_time.desc())
    result = paginate(query, page)
    result["items"] = enrich_operations(db, result["items"])
    return result


@router.get("/summary", summary="当前筛选条件下的汇总")
def operations_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    driver_id: Optional[int] = None,
    region_id: Optional[int] = None,
    pay_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = _filtered_query(
        db, start_date, end_date, vehicle_id, driver_id, region_id, None, pay_type, None, None, None
    )
    row = query.with_entities(
        func.count(models.OperationRecord.id),
        func.coalesce(func.sum(models.OperationRecord.amount), 0),
        func.coalesce(func.sum(models.OperationRecord.loaded_mileage), 0),
        func.coalesce(func.sum(models.OperationRecord.empty_mileage), 0),
        func.coalesce(func.avg(models.OperationRecord.amount), 0),
    ).first()
    total_mileage = as_float(row[2]) + as_float(row[3])
    return {
        "order_count": as_int(row[0]),
        "total_income": round(as_float(row[1]), 2),
        "loaded_mileage": round(as_float(row[2]), 2),
        "empty_mileage": round(as_float(row[3]), 2),
        "avg_amount": round(as_float(row[4]), 2),
        "empty_rate": round(as_float(row[3]) / total_mileage * 100, 2) if total_mileage else 0.0,
    }


@router.get("/pay-types", response_model=List[str], summary="支付方式字典")
def pay_types(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    rows = db.query(models.OperationRecord.pay_type).distinct().all()
    values = sorted({row[0] for row in rows if row[0]})
    return values or ["微信", "支付宝", "现金", "银行卡", "聚合支付"]


@router.get("/{record_id}", response_model=schemas.OperationRecordOut, summary="订单详情")
def get_operation(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    record = db.get(models.OperationRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="营运订单不存在")
    return enrich_operations(db, [record])[0]


@router.post("/", response_model=schemas.OperationRecordOut, summary="新增营运订单")
def create_operation(
    payload: schemas.OperationRecordCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    data = payload.model_dump()
    order_no = data.get("order_no") or f"ORD{datetime.now().strftime('%Y%m%d%H%M%S%f')[:18]}"
    data["order_no"] = order_no
    if db.query(models.OperationRecord).filter(models.OperationRecord.order_no == order_no).first():
        raise HTTPException(status_code=400, detail="订单号已存在")
    if not db.get(models.Vehicle, data["vehicle_id"]):
        raise HTTPException(status_code=400, detail="车辆不存在")
    if not db.get(models.Driver, data["driver_id"]):
        raise HTTPException(status_code=400, detail="驾驶员不存在")
    data = derive_fields(data)
    record = models.OperationRecord(**data)
    db.add(record)
    db.commit()
    db.refresh(record)
    return enrich_operations(db, [record])[0]


@router.put("/{record_id}", response_model=schemas.OperationRecordOut, summary="修改营运订单")
def update_operation(
    record_id: int,
    payload: schemas.OperationRecordUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    record = db.get(models.OperationRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="营运订单不存在")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    for key, value in updates.items():
        setattr(record, key, value)
    merged = {
        "start_time": record.start_time,
        "end_time": record.end_time,
        "loaded_mileage": record.loaded_mileage,
        "empty_mileage": record.empty_mileage,
    }
    derive_fields(merged)
    for key in ("stat_date", "hour", "weekday", "is_peak", "duration_minutes", "avg_speed"):
        setattr(record, key, merged[key])
    db.commit()
    db.refresh(record)
    return enrich_operations(db, [record])[0]


@router.delete("/{record_id}", response_model=schemas.Message, summary="删除营运订单")
def delete_operation(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    record = db.get(models.OperationRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="营运订单不存在")
    db.delete(record)
    db.commit()
    return {"message": "删除成功"}


# --------------------------------------------------------------------------
# Excel 导入 / 导出
# --------------------------------------------------------------------------


@router.get("/import/template", summary="下载导入模板")
def download_template(current_user: models.User = Depends(get_current_user)):
    frame = pd.DataFrame(
        [
            {
                "order_no": "ORD20250101001",
                "vehicle_plate": "豫A·D12345",
                "driver_name": "张伟",
                "pickup_region": "火车站广场",
                "dropoff_region": "二七商圈",
                "start_time": "2025-01-01 08:15:00",
                "end_time": "2025-01-01 08:42:00",
                "loaded_mileage": 8.6,
                "empty_mileage": 2.1,
                "amount": 25.3,
                "pay_type": "微信",
                "weather": "晴",
            }
        ]
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name="营运数据")
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=operation_import_template.xlsx"},
    )


@router.post("/import-excel", response_model=schemas.ImportResult, summary="Excel 批量导入营运数据")
async def import_operation_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    content = await file.read()
    try:
        frame = pd.read_excel(io.BytesIO(content), engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"文件解析失败：{exc}")

    frame.columns = [str(col).strip() for col in frame.columns]
    required = ["order_no", "vehicle_plate", "driver_name", "start_time", "end_time",
                "loaded_mileage", "empty_mileage", "amount"]
    missing = [col for col in required if col not in frame.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"缺少必要列：{'、'.join(missing)}。请先下载导入模板。",
        )

    plates = [str(p).strip() for p in frame["vehicle_plate"].dropna().unique().tolist()]
    names = [str(n).strip() for n in frame["driver_name"].dropna().unique().tolist()]
    vehicles = db.query(models.Vehicle).filter(models.Vehicle.plate_number.in_(plates)).all()
    drivers = db.query(models.Driver).filter(models.Driver.name.in_(names)).all()
    vehicle_map = {v.plate_number: v.id for v in vehicles}
    driver_map = {d.name: d.id for d in drivers}
    region_map = {r.name: r.id for r in db.query(models.Region).all()}

    existing = {
        row[0]
        for row in db.query(models.OperationRecord.order_no)
        .filter(models.OperationRecord.order_no.in_([str(o) for o in frame["order_no"].dropna().tolist()]))
        .all()
    }

    result = schemas.ImportResult(total_rows=len(frame))
    pending: List[dict] = []
    seen = set()

    for index, row in frame.iterrows():
        line = int(index) + 2  # Excel 行号（含表头）
        order_no = str(row["order_no"]).strip()
        if not order_no or order_no.lower() == "nan":
            result.error_rows.append(line)
            result.error_messages.append(f"第 {line} 行：订单号为空")
            continue
        if order_no in existing or order_no in seen:
            result.duplicated += 1
            continue
        plate = str(row["vehicle_plate"]).strip()
        if plate not in vehicle_map:
            result.error_rows.append(line)
            result.error_messages.append(f"第 {line} 行：车牌号 {plate} 未登记")
            continue
        driver_name = str(row["driver_name"]).strip()
        if driver_name not in driver_map:
            result.error_rows.append(line)
            result.error_messages.append(f"第 {line} 行：驾驶员 {driver_name} 未登记")
            continue
        try:
            start = pd.to_datetime(row["start_time"]).to_pydatetime()
            end = pd.to_datetime(row["end_time"]).to_pydatetime()
            data = {
                "order_no": order_no,
                "vehicle_id": vehicle_map[plate],
                "driver_id": driver_map[driver_name],
                "pickup_region_id": region_map.get(str(row.get("pickup_region", "")).strip()),
                "dropoff_region_id": region_map.get(str(row.get("dropoff_region", "")).strip()),
                "start_time": start,
                "end_time": end,
                "loaded_mileage": float(row["loaded_mileage"]),
                "empty_mileage": float(row.get("empty_mileage", 0) or 0),
                "amount": float(row["amount"]),
                "pay_type": str(row.get("pay_type", "微信")).strip() if not pd.isna(row.get("pay_type")) else "微信",
                "weather": str(row.get("weather", "晴")).strip() if not pd.isna(row.get("weather")) else "晴",
                "passenger_count": 1,
                "is_holiday": False,
            }
            pending.append(derive_fields(data))
            seen.add(order_no)
        except HTTPException as exc:
            result.error_rows.append(line)
            result.error_messages.append(f"第 {line} 行：{exc.detail}")
        except Exception as exc:  # noqa: BLE001
            result.error_rows.append(line)
            result.error_messages.append(f"第 {line} 行：{exc}")

        if len(pending) >= 2000:
            db.bulk_insert_mappings(models.OperationRecord, pending)
            db.commit()
            result.imported += len(pending)
            pending.clear()

    if pending:
        db.bulk_insert_mappings(models.OperationRecord, pending)
        db.commit()
        result.imported += len(pending)

    return result


@router.get("/export/data", summary="导出营运数据（csv / xlsx）")
def export_operations(
    fmt: str = Query("csv", pattern="^(csv|xlsx)$"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    driver_id: Optional[int] = None,
    region_id: Optional[int] = None,
    keyword: Optional[str] = None,
    pay_type: Optional[str] = None,
    limit: int = Query(50000, le=200000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = _filtered_query(
        db, start_date, end_date, vehicle_id, driver_id, region_id, keyword,
        pay_type, None, None, None,
    ).order_by(models.OperationRecord.start_time.desc()).limit(limit)
    rows = enrich_operations(db, query.all())
    columns = [
        ("order_no", "订单号"),
        ("plate_number", "车牌号"),
        ("driver_name", "驾驶员"),
        ("pickup_region_name", "上车区域"),
        ("dropoff_region_name", "下车区域"),
        ("start_time", "上车时间"),
        ("end_time", "下车时间"),
        ("loaded_mileage", "载客里程"),
        ("empty_mileage", "空驶里程"),
        ("amount", "金额"),
        ("duration_minutes", "时长(分钟)"),
        ("pay_type", "支付方式"),
        ("weather", "天气"),
    ]
    frame = pd.DataFrame(
        [{label: row.get(key) for key, label in columns} for row in rows]
    )
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    if fmt == "xlsx":
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="营运数据")
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=operations_{stamp}.xlsx"},
        )

    buffer = io.StringIO()
    buffer.write("\ufeff")  # UTF-8 BOM，保证 Excel 中文不乱码
    writer = csv.writer(buffer)
    writer.writerow([label for _, label in columns])
    for row in rows:
        writer.writerow([row.get(key) for key, _ in columns])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=operations_{stamp}.csv"},
    )
