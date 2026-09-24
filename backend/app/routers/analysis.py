from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app import models
from app.routers.auth import get_current_user

router = APIRouter()

@router.get("/income-summary")
def income_summary(
    start_date: str = Query(...),
    end_date: str = Query(...),
    group_by: str = Query("day", enum=["day", "month"]),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    date_format = "%Y-%m-%d" if group_by == "day" else "%Y-%m"
    results = db.query(
        func.date_format(models.OperationRecord.start_time, date_format).label("date"),
        func.sum(models.OperationRecord.amount).label("total_amount"),
        func.count(models.OperationRecord.id).label("order_count")
    ).filter(
        models.OperationRecord.start_time >= start,
        models.OperationRecord.start_time < end
    ).group_by("date").order_by("date").all()
    return [{"date": r.date, "total_amount": float(r.total_amount), "order_count": r.order_count} for r in results]

@router.get("/load-rate")
def load_rate(
    start_date: str,
    end_date: str,
    vehicle_id: int = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    query = db.query(
        func.sum(models.OperationRecord.loaded_mileage).label("loaded"),
        func.sum(models.OperationRecord.empty_mileage).label("empty")
    ).filter(
        models.OperationRecord.start_time >= start,
        models.OperationRecord.start_time < end
    )
    if vehicle_id:
        query = query.filter(models.OperationRecord.vehicle_id == vehicle_id)
    result = query.first()
    loaded = float(result.loaded) if result.loaded else 0
    empty = float(result.empty) if result.empty else 0
    total = loaded + empty
    rate = (loaded / total * 100) if total > 0 else 0
    return {"loaded_mileage": loaded, "empty_mileage": empty, "load_rate": round(rate, 2)}

@router.get("/driver-ranking")
def driver_ranking(
    start_date: str,
    end_date: str,
    top_n: int = 10,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    results = db.query(
        models.Driver.name,
        func.count(models.OperationRecord.id).label("order_count"),
        func.sum(models.OperationRecord.amount).label("total_income"),
        func.sum(models.OperationRecord.loaded_mileage).label("loaded_mileage")
    ).join(models.OperationRecord, models.Driver.id == models.OperationRecord.driver_id)\
     .filter(models.OperationRecord.start_time >= start, models.OperationRecord.start_time < end)\
     .group_by(models.Driver.id)\
     .order_by(func.sum(models.OperationRecord.amount).desc())\
     .limit(top_n).all()
    return [
        {"name": r.name, "order_count": r.order_count,
         "total_income": float(r.total_income), "loaded_mileage": float(r.loaded_mileage)}
        for r in results
    ]

@router.get("/abnormal-alert")
def abnormal_alert(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    vehicles = db.query(models.Vehicle).filter(models.Vehicle.status == 1).all()
    alerts = []
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    for v in vehicles:
        records = db.query(models.OperationRecord).filter(
            models.OperationRecord.vehicle_id == v.id,
            models.OperationRecord.start_time >= one_day_ago
        ).all()
        if records:
            total_loaded = sum([float(r.loaded_mileage) for r in records])
            total_empty = sum([float(r.empty_mileage) for r in records])
            total = total_loaded + total_empty
            if total > 0 and (total_empty / total) > 0.4:
                alerts.append({
                    "vehicle_plate": v.plate_number,
                    "empty_rate": round(total_empty / total * 100, 2)
                })
    return alerts