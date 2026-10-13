"""需求预测接口。"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.deps import get_current_user
from ..database import get_db
from ..services import forecast as forecast_service

router = APIRouter()


@router.get("/models", summary="可用预测模型列表")
def list_models(current_user: models.User = Depends(get_current_user)):
    return [
        {"value": key, "label": label}
        for key, label in forecast_service.MODEL_LABELS.items()
    ]


@router.get("/regions", summary="可供预测的区域（含历史数据量）")
def forecast_regions(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    counts = dict(
        db.query(models.RideRequest.region_id, func.count(models.RideRequest.id))
        .group_by(models.RideRequest.region_id)
        .all()
    )
    rows = []
    for region in db.query(models.Region).order_by(models.Region.code).all():
        rows.append(
            {
                "region_id": region.id,
                "region_name": region.name,
                "region_type": region.region_type,
                "request_count": int(counts.get(region.id, 0)),
            }
        )
    total = (
        db.query(func.count(models.RideRequest.id)).scalar() or 0
    )
    rows.insert(
        0,
        {
            "region_id": None,
            "region_name": "全域（所有区域合计）",
            "region_type": "汇总",
            "request_count": int(total),
        },
    )
    return rows


@router.post("/run", response_model=schemas.ForecastResponse, summary="执行需求预测（含滚动回测与模型对比）")
def run_forecast(
    payload: schemas.ForecastRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    horizon = int(payload.horizon or 24)
    if horizon < 1 or horizon > 168:
        raise HTTPException(status_code=400, detail="预测时长需在 1~168 小时之间")
    try:
        return forecast_service.forecast_region(
            db,
            region_id=payload.region_id,
            horizon=horizon,
            start_date=payload.start_date.isoformat() if payload.start_date else None,
            end_date=payload.end_date.isoformat() if payload.end_date else None,
            model_names=payload.models,
            auto_select=payload.auto_select,
            persist=True,
            created_by=current_user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"预测失败：{exc}")


@router.get("/quick", response_model=schemas.ForecastResponse, summary="快速预测（默认全域未来 24 小时）")
def quick_forecast(
    region_id: Optional[int] = None,
    horizon: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return forecast_service.forecast_region(
            db, region_id=region_id, horizon=horizon, persist=True,
            created_by=current_user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/accuracy", response_model=List[schemas.ForecastAccuracyOut], summary="预测准确率评估（按模型）")
def accuracy(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return forecast_service.forecast_accuracy(db, days)


@router.get("/history", summary="历史预测批次")
def forecast_history(
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(
            models.ForecastResult.batch_no,
            models.ForecastResult.model_name,
            models.ForecastResult.region_id,
            models.ForecastResult.horizon,
            models.ForecastResult.mape,
            models.ForecastResult.create_time,
            func.count(models.ForecastResult.id),
            func.min(models.ForecastResult.target_time),
            func.max(models.ForecastResult.target_time),
        )
        .group_by(
            models.ForecastResult.batch_no,
            models.ForecastResult.model_name,
            models.ForecastResult.region_id,
            models.ForecastResult.horizon,
            models.ForecastResult.mape,
            models.ForecastResult.create_time,
        )
        .order_by(models.ForecastResult.create_time.desc())
        .limit(limit)
        .all()
    )
    region_map = {r.id: r.name for r in db.query(models.Region).all()}
    return [
        {
            "batch_no": row[0],
            "model": row[1],
            "model_label": forecast_service.MODEL_LABELS.get(row[1], row[1]),
            "region_id": row[2],
            "region_name": region_map.get(row[2], "全域") if row[2] else "全域",
            "horizon": row[3],
            "mape": float(row[4]) if row[4] is not None else None,
            "create_time": row[5],
            "point_count": int(row[6]),
            "start_time": row[7],
            "end_time": row[8],
        }
        for row in rows
    ]


@router.get("/batch/{batch_no}", summary="查看某个预测批次的明细")
def forecast_batch(
    batch_no: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.ForecastResult)
        .filter(models.ForecastResult.batch_no == batch_no)
        .order_by(models.ForecastResult.target_time)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="预测批次不存在")
    return [
        {
            "target_time": row.target_time,
            "predicted_value": float(row.predicted_value),
            "lower_bound": float(row.lower_bound) if row.lower_bound is not None else None,
            "upper_bound": float(row.upper_bound) if row.upper_bound is not None else None,
            "actual_value": float(row.actual_value) if row.actual_value is not None else None,
        }
        for row in rows
    ]
