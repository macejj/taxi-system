"""车辆档案管理接口。"""
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


def enrich_vehicles(db: Session, vehicles: List[models.Vehicle]) -> List[dict]:
    """为车辆列表补充常驻区域名、当前绑定驾驶员与运营统计。"""
    if not vehicles:
        return []
    ids = [v.id for v in vehicles]

    region_map = {r.id: r.name for r in db.query(models.Region).all()}

    bindings = (
        db.query(models.VehicleDriver)
        .filter(
            models.VehicleDriver.vehicle_id.in_(ids),
            models.VehicleDriver.status == 1,
        )
        .all()
    )
    driver_map = {d.id: d.name for d in db.query(models.Driver).all()}
    bound: dict[int, tuple[int, str]] = {}
    for binding in bindings:
        bound.setdefault(binding.vehicle_id, (binding.driver_id, driver_map.get(binding.driver_id, "")))

    stats = {
        row[0]: (as_int(row[1]), as_float(row[2]))
        for row in db.query(
            models.OperationRecord.vehicle_id,
            func.count(models.OperationRecord.id),
            func.coalesce(func.sum(models.OperationRecord.amount), 0),
        )
        .filter(models.OperationRecord.vehicle_id.in_(ids))
        .group_by(models.OperationRecord.vehicle_id)
        .all()
    }

    output = []
    for vehicle in vehicles:
        item = schemas.VehicleOut.model_validate(vehicle).model_dump()
        item["home_region_name"] = region_map.get(vehicle.home_region_id)
        driver_info = bound.get(vehicle.id)
        item["bound_driver_id"] = driver_info[0] if driver_info else None
        item["bound_driver_name"] = driver_info[1] if driver_info else None
        item["order_count"], item["total_income"] = stats.get(vehicle.id, (0, 0.0))
        output.append(item)
    return output


@router.get("/", response_model=schemas.Page[schemas.VehicleOut], summary="车辆分页列表")
def list_vehicles(
    keyword: Optional[str] = Query(None, description="车牌号或品牌型号"),
    status: Optional[int] = None,
    home_region_id: Optional[int] = None,
    vehicle_type: Optional[str] = None,
    energy_type: Optional[str] = None,
    expiring: Optional[int] = Query(None, description="筛选 N 天内保险/营运证/保养到期的车辆"),
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Vehicle)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            models.Vehicle.plate_number.like(like) | models.Vehicle.brand_model.like(like)
        )
    if status is not None:
        query = query.filter(models.Vehicle.status == status)
    if home_region_id:
        query = query.filter(models.Vehicle.home_region_id == home_region_id)
    if vehicle_type:
        query = query.filter(models.Vehicle.vehicle_type == vehicle_type)
    if energy_type:
        query = query.filter(models.Vehicle.energy_type == energy_type)
    if expiring:
        limit = date.today() + timedelta(days=expiring)
        query = query.filter(
            (models.Vehicle.insurance_expire <= limit)
            | (models.Vehicle.cert_expire <= limit)
            | (models.Vehicle.next_maintenance_date <= limit)
        )
    query = query.order_by(models.Vehicle.id.desc())
    result = paginate(query, page)
    result["items"] = enrich_vehicles(db, result["items"])
    return result


@router.get("/all", response_model=List[schemas.VehicleOut], summary="全部在营车辆（下拉选项）")
def list_all_vehicles(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    vehicles = (
        db.query(models.Vehicle).filter(models.Vehicle.status == 1).order_by(models.Vehicle.plate_number).all()
    )
    return enrich_vehicles(db, vehicles)


@router.get("/dictionaries", summary="车辆相关字典")
def vehicle_dictionaries(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return {
        "vehicle_type": ["巡游出租车", "网约车", "新能源出租车", "租赁出租车"],
        "energy_type": ["燃油", "纯电", "混动", "天然气"],
        "status": [
            {"value": 1, "label": "在营"},
            {"value": 0, "label": "停运"},
            {"value": 2, "label": "维修"},
        ],
    }


@router.get("/{vehicle_id}", response_model=schemas.VehicleOut, summary="车辆详情")
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    vehicle = db.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    return enrich_vehicles(db, [vehicle])[0]


@router.post("/", response_model=schemas.VehicleOut, summary="新增车辆")
def create_vehicle(
    payload: schemas.VehicleBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if db.query(models.Vehicle).filter(models.Vehicle.plate_number == payload.plate_number).first():
        raise HTTPException(status_code=400, detail="车牌号已存在")
    vehicle = models.Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return enrich_vehicles(db, [vehicle])[0]


@router.put("/{vehicle_id}", response_model=schemas.VehicleOut, summary="修改车辆")
def update_vehicle(
    vehicle_id: int,
    payload: schemas.VehicleBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    vehicle = db.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    duplicate = (
        db.query(models.Vehicle)
        .filter(models.Vehicle.plate_number == payload.plate_number, models.Vehicle.id != vehicle_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="车牌号已存在")
    for key, value in payload.model_dump().items():
        setattr(vehicle, key, value)
    db.commit()
    db.refresh(vehicle)
    return enrich_vehicles(db, [vehicle])[0]


@router.patch("/{vehicle_id}/status", response_model=schemas.Message, summary="变更车辆状态")
def update_vehicle_status(
    vehicle_id: int,
    status: int = Query(..., ge=0, le=2, description="1 在营 0 停运 2 维修"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    vehicle = db.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    vehicle.status = status
    db.commit()
    return {"message": "状态已更新"}


@router.delete("/{vehicle_id}", response_model=schemas.Message, summary="删除车辆")
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    vehicle = db.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="车辆不存在")
    records = (
        db.query(func.count(models.OperationRecord.id))
        .filter(models.OperationRecord.vehicle_id == vehicle_id)
        .scalar()
    )
    if records:
        raise HTTPException(
            status_code=400,
            detail=f"该车辆已产生 {records} 条营运记录，不能删除；可将状态改为停运",
        )
    db.query(models.VehicleDriver).filter(models.VehicleDriver.vehicle_id == vehicle_id).delete()
    db.delete(vehicle)
    db.commit()
    return {"message": "删除成功"}
