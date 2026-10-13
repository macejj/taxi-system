"""驾驶员档案管理接口。"""
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..core.deps import PageParams, get_current_user, paginate
from ..core.sqlutil import as_float, as_int
from ..database import get_db

router = APIRouter()


def enrich_drivers(db: Session, drivers: List[models.Driver]) -> List[dict]:
    """补充常驻区域、当前绑定车辆与运营统计。"""
    if not drivers:
        return []
    ids = [d.id for d in drivers]
    region_map = {r.id: r.name for r in db.query(models.Region).all()}
    plate_map = {v.id: v.plate_number for v in db.query(models.Vehicle).all()}

    bindings = (
        db.query(models.VehicleDriver)
        .filter(
            models.VehicleDriver.driver_id.in_(ids),
            models.VehicleDriver.status == 1,
        )
        .all()
    )
    bound: dict[int, tuple[int, str]] = {}
    for binding in bindings:
        bound.setdefault(binding.driver_id, (binding.vehicle_id, plate_map.get(binding.vehicle_id, "")))

    stats = {
        row[0]: (as_int(row[1]), as_float(row[2]))
        for row in db.query(
            models.OperationRecord.driver_id,
            func.count(models.OperationRecord.id),
            func.coalesce(func.sum(models.OperationRecord.amount), 0),
        )
        .filter(models.OperationRecord.driver_id.in_(ids))
        .group_by(models.OperationRecord.driver_id)
        .all()
    }

    output = []
    for driver in drivers:
        item = schemas.DriverOut.model_validate(driver).model_dump()
        item["home_region_name"] = region_map.get(driver.home_region_id)
        info = bound.get(driver.id)
        item["bound_vehicle_id"] = info[0] if info else None
        item["bound_plate"] = info[1] if info else None
        item["order_count"], item["total_income"] = stats.get(driver.id, (0, 0.0))
        output.append(item)
    return output


@router.get("/", response_model=schemas.Page[schemas.DriverOut], summary="驾驶员分页列表")
def list_drivers(
    keyword: Optional[str] = Query(None, description="姓名 / 身份证号 / 电话"),
    status: Optional[int] = None,
    home_region_id: Optional[int] = None,
    expiring: Optional[int] = Query(None, description="N 天内驾驶证到期"),
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Driver)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            models.Driver.name.like(like)
            | models.Driver.id_card.like(like)
            | models.Driver.phone.like(like)
        )
    if status is not None:
        query = query.filter(models.Driver.status == status)
    if home_region_id:
        query = query.filter(models.Driver.home_region_id == home_region_id)
    if expiring:
        query = query.filter(models.Driver.license_expire <= date.today() + timedelta(days=expiring))
    query = query.order_by(models.Driver.id.desc())
    result = paginate(query, page)
    result["items"] = enrich_drivers(db, result["items"])
    return result


@router.get("/all", response_model=List[schemas.DriverOut], summary="全部在职驾驶员（下拉选项）")
def list_all_drivers(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    drivers = (
        db.query(models.Driver).filter(models.Driver.status == 1).order_by(models.Driver.name).all()
    )
    return enrich_drivers(db, drivers)


@router.get("/{driver_id}", response_model=schemas.DriverOut, summary="驾驶员详情")
def get_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    driver = db.get(models.Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="驾驶员不存在")
    return enrich_drivers(db, [driver])[0]


@router.post("/", response_model=schemas.DriverOut, summary="新增驾驶员")
def create_driver(
    payload: schemas.DriverBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if db.query(models.Driver).filter(models.Driver.id_card == payload.id_card).first():
        raise HTTPException(status_code=400, detail="身份证号已存在")
    driver = models.Driver(**payload.model_dump())
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return enrich_drivers(db, [driver])[0]


@router.put("/{driver_id}", response_model=schemas.DriverOut, summary="修改驾驶员")
def update_driver(
    driver_id: int,
    payload: schemas.DriverBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    driver = db.get(models.Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="驾驶员不存在")
    duplicate = (
        db.query(models.Driver)
        .filter(models.Driver.id_card == payload.id_card, models.Driver.id != driver_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="身份证号已存在")
    for key, value in payload.model_dump().items():
        setattr(driver, key, value)
    db.commit()
    db.refresh(driver)
    return enrich_drivers(db, [driver])[0]


@router.delete("/{driver_id}", response_model=schemas.Message, summary="删除驾驶员")
def delete_driver(
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    driver = db.get(models.Driver, driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="驾驶员不存在")
    records = (
        db.query(func.count(models.OperationRecord.id))
        .filter(models.OperationRecord.driver_id == driver_id)
        .scalar()
    )
    if records:
        raise HTTPException(
            status_code=400,
            detail=f"该驾驶员已产生 {records} 条营运记录，不能删除；可将状态改为离职",
        )
    db.query(models.VehicleDriver).filter(models.VehicleDriver.driver_id == driver_id).delete()
    db.delete(driver)
    db.commit()
    return {"message": "删除成功"}
