"""系统管理接口：用户、参数配置、操作日志、数据维护。"""
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.config_store import ensure_defaults, list_configs, load_overrides
from ..core.deps import PageParams, get_current_user, paginate, require_admin
from ..core.security import get_password_hash
from ..database import get_db
from ..services import simulator

router = APIRouter()

VALID_ROLES = ("admin", "operator", "viewer")


# --------------------------------------------------------------------------
# 用户管理
# --------------------------------------------------------------------------


@router.get("/users", response_model=schemas.Page[schemas.UserOut], summary="用户列表")
def list_users(
    keyword: Optional[str] = None,
    role: Optional[str] = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    query = db.query(models.User)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            models.User.username.like(like) | models.User.real_name.like(like)
        )
    if role:
        query = query.filter(models.User.role == role)
    query = query.order_by(models.User.id)
    return paginate(query, page)


@router.post("/users", response_model=schemas.UserOut, summary="新增用户")
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"角色只能是 {'/'.join(VALID_ROLES)}")
    if db.query(models.User).filter(models.User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = models.User(
        username=payload.username,
        password_hash=get_password_hash(payload.password),
        real_name=payload.real_name,
        role=payload.role,
        phone=payload.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=schemas.UserOut, summary="修改用户")
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    data = payload.model_dump(exclude_none=True)
    if "role" in data and data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"角色只能是 {'/'.join(VALID_ROLES)}")
    if user.id == current_user.id and data.get("status") == 0:
        raise HTTPException(status_code=400, detail="不能禁用当前登录账号")
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", response_model=schemas.Message, summary="重置用户密码")
def reset_password(
    user_id: int,
    payload: schemas.PasswordReset,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    return {"message": f"用户 {user.username} 的密码已重置"}


@router.delete("/users/{user_id}", response_model=schemas.Message, summary="删除用户")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="内置管理员账号不能删除")
    db.delete(user)
    db.commit()
    return {"message": "删除成功"}


# --------------------------------------------------------------------------
# 参数配置
# --------------------------------------------------------------------------


@router.get("/configs", response_model=List[schemas.SysConfigOut], summary="参数配置列表")
def get_configs(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    ensure_defaults(db)
    return list_configs(db)


@router.put("/configs/{config_key}", response_model=schemas.SysConfigOut, summary="修改参数配置")
def update_config(
    config_key: str,
    payload: schemas.SysConfigUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    row = db.query(models.SysConfig).filter(models.SysConfig.config_key == config_key).first()
    if not row:
        raise HTTPException(status_code=404, detail="配置项不存在")
    raw = payload.config_value.strip()
    try:
        if row.value_type == "int":
            int(float(raw))
        elif row.value_type == "float":
            float(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"配置项 {config_key} 需要{'整数' if row.value_type == 'int' else '数值'}")
    row.config_value = raw
    row.update_time = datetime.now()
    db.commit()
    load_overrides(db)
    db.refresh(row)
    return row


@router.post("/configs/reload", response_model=schemas.Message, summary="重新载入参数配置")
def reload_configs(
    db: Session = Depends(get_db), current_user: models.User = Depends(require_admin)
):
    ensure_defaults(db)
    applied = load_overrides(db)
    return {"message": f"已重新载入 {len(applied)} 项配置"}


# --------------------------------------------------------------------------
# 操作日志
# --------------------------------------------------------------------------


@router.get("/logs", response_model=schemas.Page[schemas.OperationLogOut], summary="操作日志")
def list_logs(
    keyword: Optional[str] = None,
    module: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=365),
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.OperationLog)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            models.OperationLog.username.like(like)
            | models.OperationLog.operation.like(like)
            | models.OperationLog.path.like(like)
        )
    if module:
        query = query.filter(models.OperationLog.module == module)
    if days:
        query = query.filter(
            models.OperationLog.create_time >= datetime.now() - timedelta(days=days)
        )
    query = query.order_by(models.OperationLog.id.desc())
    result = paginate(query, page)
    return result


@router.delete("/logs", response_model=schemas.Message, summary="清空操作日志")
def clear_logs(
    days: int = Query(30, ge=0, le=3650, description="清理多少天以前的日志，0 表示全部清空"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    query = db.query(models.OperationLog)
    if days > 0:
        query = query.filter(
            models.OperationLog.create_time < datetime.now() - timedelta(days=days)
        )
    count = query.delete(synchronize_session=False)
    db.commit()
    return {"message": f"已清理 {count} 条操作日志"}


# --------------------------------------------------------------------------
# 数据维护
# --------------------------------------------------------------------------


@router.get("/data/stats", summary="数据量统计")
def data_stats(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return {
        "region": db.query(func.count(models.Region.id)).scalar() or 0,
        "vehicle": db.query(func.count(models.Vehicle.id)).scalar() or 0,
        "driver": db.query(func.count(models.Driver.id)).scalar() or 0,
        "vehicle_driver": db.query(func.count(models.VehicleDriver.id)).scalar() or 0,
        "ride_request": db.query(func.count(models.RideRequest.id)).scalar() or 0,
        "operation_record": db.query(func.count(models.OperationRecord.id)).scalar() or 0,
        "dispatch_plan": db.query(func.count(models.DispatchPlan.id)).scalar() or 0,
        "dispatch_order": db.query(func.count(models.DispatchOrder.id)).scalar() or 0,
        "forecast_result": db.query(func.count(models.ForecastResult.id)).scalar() or 0,
        "sys_user": db.query(func.count(models.User.id)).scalar() or 0,
        "operation_log": db.query(func.count(models.OperationLog.id)).scalar() or 0,
    }


@router.post("/data/simulate", summary="生成仿真运营数据")
def simulate_data(
    days: int = Query(60, ge=7, le=365, description="生成最近多少天的运营流水"),
    vehicles: int = Query(60, ge=5, le=500),
    drivers: int = Query(80, ge=5, le=800),
    seed: int = Query(20240501),
    reset: bool = Query(True, description="是否先清空现有业务数据"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """一键生成可复现的演示数据（车辆、驾驶员、叫车请求、营运订单）。"""
    try:
        result = simulator.run_simulation(
            db, days=days, vehicles=vehicles, drivers=drivers, seed=seed,
            reset=reset, verbose=False,
        )
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail=f"数据生成失败：{exc}")
    return {"message": "仿真数据生成完成", **result}


@router.delete("/data/clear", summary="清空业务数据")
def clear_data(
    include_master: bool = Query(True, description="是否同时清空车辆/驾驶员/区域等基础档案"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    simulator.DataSimulator(db, verbose=False).reset(include_master=include_master)
    return {"message": "业务数据已清空"}
