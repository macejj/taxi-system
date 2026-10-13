"""人车绑定（排班）管理接口。"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.deps import PageParams, get_current_user, paginate
from ..database import get_db

router = APIRouter()


def _enrich(db: Session, rows: List[models.VehicleDriver]) -> List[dict]:
    plate_map = {v.id: v.plate_number for v in db.query(models.Vehicle).all()}
    driver_map = {d.id: d for d in db.query(models.Driver).all()}
    output = []
    for row in rows:
        driver = driver_map.get(row.driver_id)
        item = schemas.AssignmentOut.model_validate(row).model_dump()
        item["plate_number"] = plate_map.get(row.vehicle_id)
        item["driver_name"] = driver.name if driver else None
        item["driver_phone"] = driver.phone if driver else None
        output.append(item)
    return output


@router.get("/", response_model=schemas.Page[schemas.AssignmentOut], summary="绑定记录分页列表")
def list_assignments(
    vehicle_id: Optional[int] = None,
    driver_id: Optional[int] = None,
    status: Optional[int] = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.VehicleDriver)
    if vehicle_id:
        query = query.filter(models.VehicleDriver.vehicle_id == vehicle_id)
    if driver_id:
        query = query.filter(models.VehicleDriver.driver_id == driver_id)
    if status is not None:
        query = query.filter(models.VehicleDriver.status == status)
    query = query.order_by(models.VehicleDriver.status.desc(), models.VehicleDriver.id.desc())
    result = paginate(query, page)
    result["items"] = _enrich(db, result["items"])
    return result


@router.post("/", response_model=schemas.AssignmentOut, summary="新增绑定（排班）")
def create_assignment(
    payload: schemas.AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    vehicle = db.get(models.Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    driver = db.get(models.Driver, payload.driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="驾驶员不存在")

    exists = (
        db.query(models.VehicleDriver)
        .filter(
            models.VehicleDriver.vehicle_id == payload.vehicle_id,
            models.VehicleDriver.driver_id == payload.driver_id,
            models.VehicleDriver.status == 1,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="该车辆与该驾驶员已存在生效中的绑定关系")

    others = (
        db.query(models.VehicleDriver)
        .filter(
            models.VehicleDriver.vehicle_id == payload.vehicle_id,
            models.VehicleDriver.status == 1,
            models.VehicleDriver.shift == payload.shift,
        )
        .count()
    )
    if others >= 2:
        raise HTTPException(status_code=400, detail=f"该车辆{payload.shift}已绑定 2 名驾驶员，请先解绑")

    binding = models.VehicleDriver(
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        assign_date=payload.assign_date or date.today(),
        shift=payload.shift,
        status=1,
        remark=payload.remark,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)
    return _enrich(db, [binding])[0]


@router.delete("/{binding_id}", response_model=schemas.Message, summary="解绑（结束排班）")
def delete_assignment(
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    binding = db.get(models.VehicleDriver, binding_id)
    if not binding:
        raise HTTPException(status_code=404, detail="绑定记录不存在")
    # 保留历史记录，仅结束绑定
    binding.status = 0
    binding.unassign_date = date.today()
    db.commit()
    return {"message": "已解绑"}
