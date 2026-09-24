from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
import pandas as pd
import io
from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=schemas.OperationRecordOut)
def create_operation(record: schemas.OperationRecordCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if db.query(models.OperationRecord).filter(models.OperationRecord.order_no == record.order_no).first():
        raise HTTPException(status_code=400, detail="订单号已存在")
    db_record = models.OperationRecord(**record.dict())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record

@router.get("/", response_model=list[schemas.OperationRecordOut])
def list_operations(
    start_date: str = None,
    end_date: str = None,
    vehicle_id: int = None,
    driver_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    query = db.query(models.OperationRecord)
    if start_date:
        query = query.filter(models.OperationRecord.start_time >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        query = query.filter(models.OperationRecord.start_time < datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1))
    if vehicle_id:
        query = query.filter(models.OperationRecord.vehicle_id == vehicle_id)
    if driver_id:
        query = query.filter(models.OperationRecord.driver_id == driver_id)
    return query.offset(skip).limit(limit).all()

@router.post("/import-excel")
async def import_operation_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
    required_columns = ['order_no', 'vehicle_plate', 'driver_name', 'start_time', 'end_time',
                        'loaded_mileage', 'empty_mileage', 'amount', 'pay_type']
    if not all(col in df.columns for col in required_columns):
        raise HTTPException(status_code=400, detail=f"缺少必要列，请使用模板")

    plates = df['vehicle_plate'].dropna().unique().tolist()
    driver_names = df['driver_name'].dropna().unique().tolist()
    vehicles = db.query(models.Vehicle).filter(models.Vehicle.plate_number.in_(plates)).all()
    drivers = db.query(models.Driver).filter(models.Driver.name.in_(driver_names)).all()
    vehicle_map = {v.plate_number: v.id for v in vehicles}
    driver_map = {d.name: d.id for d in drivers}

    success_count = 0
    error_rows = []
    records = []
    for idx, row in df.iterrows():
        if pd.isna(row['vehicle_plate']) or row['vehicle_plate'] not in vehicle_map:
            error_rows.append(idx + 2)
            continue
        if pd.isna(row['driver_name']) or row['driver_name'] not in driver_map:
            error_rows.append(idx + 2)
            continue
        order_no = str(row['order_no'])
        if db.query(models.OperationRecord).filter(models.OperationRecord.order_no == order_no).first():
            error_rows.append(idx + 2)
            continue
        try:
            rec = models.OperationRecord(
                order_no=order_no,
                vehicle_id=vehicle_map[row['vehicle_plate']],
                driver_id=driver_map[row['driver_name']],
                start_time=pd.to_datetime(row['start_time']).to_pydatetime(),
                end_time=pd.to_datetime(row['end_time']).to_pydatetime(),
                loaded_mileage=float(row['loaded_mileage']),
                empty_mileage=float(row['empty_mileage']),
                amount=float(row['amount']),
                pay_type=str(row['pay_type']) if not pd.isna(row['pay_type']) else None
            )
            records.append(rec)
            success_count += 1
            if len(records) >= 500:
                db.bulk_save_objects(records)
                db.commit()
                records = []
        except Exception:
            error_rows.append(idx + 2)
    if records:
        db.bulk_save_objects(records)
        db.commit()
    return {"success": True, "imported": success_count, "error_rows": error_rows}