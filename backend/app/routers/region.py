"""运营区域管理接口。"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.deps import PageParams, get_current_user, paginate
from ..database import get_db

router = APIRouter()


@router.get("/all", response_model=List[schemas.RegionOut], summary="全部启用区域（下拉选项）")
def list_all_regions(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return (
        db.query(models.Region)
        .filter(models.Region.status == 1)
        .order_by(models.Region.code)
        .all()
    )


@router.get("/", response_model=schemas.Page[schemas.RegionOut], summary="区域分页列表")
def list_regions(
    keyword: Optional[str] = Query(None, description="名称或编码模糊查询"),
    region_type: Optional[str] = None,
    status: Optional[int] = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Region)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            models.Region.name.like(like) | models.Region.code.like(like)
        )
    if region_type:
        query = query.filter(models.Region.region_type == region_type)
    if status is not None:
        query = query.filter(models.Region.status == status)
    query = query.order_by(models.Region.code)
    return paginate(query, page)


@router.get("/types", response_model=List[str], summary="区域类型字典")
def region_types(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    rows = db.query(models.Region.region_type).distinct().all()
    types = sorted({row[0] for row in rows if row[0]})
    return types or ["交通枢纽", "商圈", "居民区", "学校", "景区", "医院", "工业区"]


@router.get("/{region_id}", response_model=schemas.RegionOut, summary="区域详情")
def get_region(
    region_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    region = db.get(models.Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="区域不存在")
    return region


@router.post("/", response_model=schemas.RegionOut, summary="新增区域")
def create_region(
    payload: schemas.RegionBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if db.query(models.Region).filter(models.Region.code == payload.code).first():
        raise HTTPException(status_code=400, detail="区域编码已存在")
    region = models.Region(**payload.model_dump())
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


@router.put("/{region_id}", response_model=schemas.RegionOut, summary="修改区域")
def update_region(
    region_id: int,
    payload: schemas.RegionBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    region = db.get(models.Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="区域不存在")
    duplicate = (
        db.query(models.Region)
        .filter(models.Region.code == payload.code, models.Region.id != region_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="区域编码已存在")
    for key, value in payload.model_dump().items():
        setattr(region, key, value)
    db.commit()
    db.refresh(region)
    return region


@router.delete("/{region_id}", response_model=schemas.Message, summary="删除区域")
def delete_region(
    region_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    region = db.get(models.Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="区域不存在")
    used = (
        db.query(func.count(models.OperationRecord.id))
        .filter(
            (models.OperationRecord.pickup_region_id == region_id)
            | (models.OperationRecord.dropoff_region_id == region_id)
        )
        .scalar()
    )
    if used:
        raise HTTPException(
            status_code=400,
            detail=f"该区域已关联 {used} 条营运记录，无法删除；可将其状态改为停用",
        )
    if db.query(func.count(models.RideRequest.id)).filter(models.RideRequest.region_id == region_id).scalar():
        raise HTTPException(status_code=400, detail="该区域存在叫车需求数据，无法删除；可将其状态改为停用")
    db.delete(region)
    db.commit()
    return {"message": "删除成功"}
