from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user

router = APIRouter()

@router.post("/", response_model=schemas.DriverOut)
def create_driver(driver: schemas.DriverBase, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if db.query(models.Driver).filter(models.Driver.id_card == driver.id_card).first():
        raise HTTPException(status_code=400, detail="身份证号已存在")
    db_driver = models.Driver(**driver.dict())
    db.add(db_driver)
    db.commit()
    db.refresh(db_driver)
    return db_driver

@router.get("/", response_model=list[schemas.DriverOut])
def list_drivers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return db.query(models.Driver).offset(skip).limit(limit).all()

@router.get("/{driver_id}", response_model=schemas.DriverOut)
def get_driver(driver_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="驾驶员不存在")
    return driver

@router.put("/{driver_id}", response_model=schemas.DriverOut)
def update_driver(driver_id: int, driver: schemas.DriverBase, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
    if not db_driver:
        raise HTTPException(status_code=404, detail="驾驶员不存在")
    if db.query(models.Driver).filter(models.Driver.id_card == driver.id_card, models.Driver.id != driver_id).first():
        raise HTTPException(status_code=400, detail="身份证号已存在")
    for key, value in driver.dict().items():
        setattr(db_driver, key, value)
    db.commit()
    db.refresh(db_driver)
    return db_driver

@router.delete("/{driver_id}")
def delete_driver(driver_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    db_driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
    if not db_driver:
        raise HTTPException(status_code=404, detail="驾驶员不存在")
    db.delete(db_driver)
    db.commit()
    return {"message": "删除成功"}