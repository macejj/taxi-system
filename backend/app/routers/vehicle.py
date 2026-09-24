from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=schemas.VehicleOut)
def create_vehicle(vehicle: schemas.VehicleBase, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    exists = db.query(models.Vehicle).filter(models.Vehicle.plate_number == vehicle.plate_number).first()
    if exists:
        raise HTTPException(status_code=400, detail="车牌号已存在")
    db_vehicle = models.Vehicle(**vehicle.dict())
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle

@router.get("/", response_model=list[schemas.VehicleOut])
def list_vehicles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    vehicles = db.query(models.Vehicle).offset(skip).limit(limit).all()
    return vehicles

@router.get("/{vehicle_id}", response_model=schemas.VehicleOut)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    return vehicle

@router.put("/{vehicle_id}", response_model=schemas.VehicleOut)
def update_vehicle(vehicle_id: int, vehicle: schemas.VehicleBase, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not db_vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    duplicate = db.query(models.Vehicle).filter(models.Vehicle.plate_number == vehicle.plate_number, models.Vehicle.id != vehicle_id).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="车牌号已存在")
    for key, value in vehicle.dict().items():
        setattr(db_vehicle, key, value)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle

@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_vehicle = db.query(models.Vehicle).filter(models.Vehicle.id == vehicle_id).first()
    if not db_vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    db.delete(db_vehicle)
    db.commit()
    return {"message": "删除成功"}