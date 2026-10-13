"""调度决策支持接口。"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.deps import PageParams, get_current_user, paginate
from ..database import get_db
from ..services import dispatch as dispatch_service

router = APIRouter()

STATUS_TEXT = {0: "待执行", 1: "执行中", 2: "已完成", 3: "已拒绝", 4: "已取消"}
PLAN_STATUS_TEXT = {0: "草稿", 1: "已下发", 2: "执行中", 3: "已完成", 4: "已取消"}


def enrich_orders(db: Session, orders: List[models.DispatchOrder]) -> List[dict]:
    if not orders:
        return []
    plate_map = {v.id: v.plate_number for v in db.query(models.Vehicle).all()}
    driver_map = {d.id: d.name for d in db.query(models.Driver).all()}
    region_map = {r.id: r.name for r in db.query(models.Region).all()}
    output = []
    for order in orders:
        item = schemas.DispatchOrderOut.model_validate(order).model_dump()
        item["plate_number"] = plate_map.get(order.vehicle_id)
        item["driver_name"] = driver_map.get(order.driver_id)
        item["from_region_name"] = region_map.get(order.from_region_id)
        item["to_region_name"] = region_map.get(order.to_region_id)
        item["status_text"] = STATUS_TEXT.get(order.status, "未知")
        output.append(item)
    return output


def enrich_plans(db: Session, plans: List[models.DispatchPlan], with_orders: bool = False) -> List[dict]:
    if not plans:
        return []
    ids = [p.id for p in plans]
    done_map = dict(
        db.query(models.DispatchOrder.plan_id, func.count(models.DispatchOrder.id))
        .filter(
            models.DispatchOrder.plan_id.in_(ids),
            models.DispatchOrder.status.in_((1, 2)),
        )
        .group_by(models.DispatchOrder.plan_id)
        .all()
    )
    output = []
    for plan in plans:
        item = schemas.DispatchPlanOut.model_validate(plan).model_dump()
        item["status_text"] = PLAN_STATUS_TEXT.get(plan.status, "未知")
        item["done_count"] = int(done_map.get(plan.id, 0))
        if with_orders:
            item["orders"] = enrich_orders(db, plan.orders)
        output.append(item)
    return output


# --------------------------------------------------------------------------
# 供需态势与方案生成
# --------------------------------------------------------------------------


@router.get("/region-status", summary="目标时段各区域供需状态")
def region_status(
    target_date: Optional[str] = None,
    target_hour: Optional[int] = Query(None, ge=0, le=23, description="不传则自动选择缺口最大的时段"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    now = datetime.now()
    auto_selected = target_hour is None
    try:
        if target_hour is None:
            if target_date:
                day = date.fromisoformat(target_date)
                earliest = now.hour + 1 if day == now.date() else 0
                hour, _ = dispatch_service.peak_hour_in_day(db, day, earliest)
            else:
                day, hour, _ = dispatch_service.pick_peak_hour(db, now)
        else:
            hour = int(target_hour)
            day = date.fromisoformat(target_date) if target_date else now.date()
        states, method = dispatch_service.build_region_states(db, day, hour)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    payload = [s.to_dict() for s in states]
    payload.sort(key=lambda item: item["gap"], reverse=True)
    return {
        "target_date": day.isoformat(),
        "target_hour": hour,
        "auto_selected": auto_selected,
        "method": method,
        "items": payload,
    }


@router.post("/generate", response_model=schemas.DispatchGenerateResponse, summary="生成调度方案")
def generate_plan(
    payload: schemas.DispatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.strategy not in ("greedy", "hungarian"):
        raise HTTPException(status_code=400, detail="调度策略只能是 greedy 或 hungarian")
    try:
        result = dispatch_service.generate_dispatch_plan(
            db,
            plan_date=payload.plan_date,
            target_hour=payload.target_hour,
            strategy=payload.strategy,
            auto_save=payload.auto_save,
            created_by=current_user.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    plan = result["plan"]
    return {
        "plan": plan,
        "region_status": result["region_status"],
        "strategy_compare": result["strategy_compare"],
        "warnings": result["warnings"],
    }


# --------------------------------------------------------------------------
# 方案与调度单管理
# --------------------------------------------------------------------------


@router.get("/plans", summary="调度方案列表")
def list_plans(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[int] = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.DispatchPlan)
    if start_date:
        query = query.filter(models.DispatchPlan.plan_date >= date.fromisoformat(start_date))
    if end_date:
        query = query.filter(models.DispatchPlan.plan_date <= date.fromisoformat(end_date))
    if status is not None:
        query = query.filter(models.DispatchPlan.status == status)
    query = query.order_by(models.DispatchPlan.id.desc())
    result = paginate(query, page)
    result["items"] = enrich_plans(db, result["items"])
    return result


@router.get("/plans/{plan_id}", response_model=schemas.DispatchPlanOut, summary="调度方案详情")
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    plan = db.get(models.DispatchPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="调度方案不存在")
    return enrich_plans(db, [plan], with_orders=True)[0]


@router.patch("/plans/{plan_id}/status", response_model=schemas.Message, summary="更新方案状态")
def update_plan_status(
    plan_id: int,
    status: int = Query(..., ge=0, le=4),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    plan = db.get(models.DispatchPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="调度方案不存在")
    plan.status = status
    db.commit()
    return {"message": "方案状态已更新"}


@router.delete("/plans/{plan_id}", response_model=schemas.Message, summary="删除调度方案")
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    plan = db.get(models.DispatchPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="调度方案不存在")
    if plan.status in (1, 2):
        raise HTTPException(status_code=400, detail="已下发或执行中的方案不能删除")
    db.delete(plan)
    db.commit()
    return {"message": "删除成功"}


@router.get("/orders", response_model=schemas.Page[schemas.DispatchOrderOut], summary="调度单列表")
def list_orders(
    plan_id: Optional[int] = None,
    status: Optional[int] = None,
    to_region_id: Optional[int] = None,
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.DispatchOrder)
    if plan_id:
        query = query.filter(models.DispatchOrder.plan_id == plan_id)
    if status is not None:
        query = query.filter(models.DispatchOrder.status == status)
    if to_region_id:
        query = query.filter(models.DispatchOrder.to_region_id == to_region_id)
    query = query.order_by(models.DispatchOrder.id.desc())
    result = paginate(query, page)
    result["items"] = enrich_orders(db, result["items"])
    return result


@router.post("/orders/{order_id}/feedback", response_model=schemas.DispatchOrderOut, summary="提交调度执行反馈")
def submit_feedback(
    order_id: int,
    payload: schemas.DispatchFeedback,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    order = db.get(models.DispatchOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="调度单不存在")
    if order.status in (2, 3, 4):
        raise HTTPException(status_code=400, detail=f"调度单已处于「{STATUS_TEXT.get(order.status)}」状态，不能重复提交")
    if payload.status not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="反馈状态只能是 1 执行中 / 2 已完成 / 3 已拒绝 / 4 已取消")
    order.status = payload.status
    order.feedback = payload.feedback
    if payload.status in (2, 3, 4):
        order.executed_time = datetime.now()
    db.commit()
    # 若方案内所有调度单都已结束，则把方案标记为已完成
    plan = db.get(models.DispatchPlan, order.plan_id)
    if plan:
        pending = (
            db.query(func.count(models.DispatchOrder.id))
            .filter(
                models.DispatchOrder.plan_id == plan.id,
                models.DispatchOrder.status.in_((0, 1)),
            )
            .scalar()
        )
        if not pending:
            plan.status = 3
            db.commit()
    db.refresh(order)
    return enrich_orders(db, [order])[0]


@router.get("/plans/{plan_id}/effect", response_model=schemas.DispatchEffectOut, summary="调度效果评估")
def plan_effect(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return dispatch_service.evaluate_plan(db, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/strategy-compare", summary="调度策略对比实验（贪心 vs 匈牙利）")
def strategy_compare(
    hours: int = Query(24, ge=1, le=72, description="在未来多少个整点上做对比"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    try:
        return dispatch_service.compare_strategies(db, hours=hours)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/strategy-benchmark", summary="指派算法基准实验（不同规模随机算例）")
def strategy_benchmark(
    instances: int = Query(200, ge=10, le=2000, description="每个规模下的随机算例数量"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return dispatch_service.benchmark_assignment(n_instances=instances)


@router.get("/statistics", summary="调度统计（按日/策略）")
def dispatch_statistics(
    days: int = Query(30, ge=1, le=180),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    since = date.today() - timedelta(days=days - 1)
    plans = (
        db.query(models.DispatchPlan)
        .filter(models.DispatchPlan.plan_date >= since)
        .all()
    )
    orders = (
        db.query(models.DispatchOrder)
        .join(models.DispatchPlan, models.DispatchPlan.id == models.DispatchOrder.plan_id)
        .filter(models.DispatchPlan.plan_date >= since)
        .all()
    )
    by_status: dict[int, int] = {}
    for order in orders:
        by_status[order.status] = by_status.get(order.status, 0) + 1

    by_strategy: dict[str, dict] = {}
    for plan in plans:
        item = by_strategy.setdefault(
            plan.strategy or "unknown",
            {"strategy": plan.strategy, "plan_count": 0, "dispatch_count": 0, "expected_gain": 0.0},
        )
        item["plan_count"] += 1
        item["dispatch_count"] += int(plan.dispatch_count or 0)
        item["expected_gain"] += float(plan.expected_gain or 0)

    daily: dict[str, dict] = {}
    for plan in plans:
        key = plan.plan_date.isoformat()
        item = daily.setdefault(key, {"date": key, "dispatch_count": 0, "expected_gain": 0.0, "plan_count": 0})
        item["dispatch_count"] += int(plan.dispatch_count or 0)
        item["expected_gain"] += float(plan.expected_gain or 0)
        item["plan_count"] += 1

    return {
        "days": days,
        "plan_count": len(plans),
        "order_count": len(orders),
        "expected_gain": round(sum(float(p.expected_gain or 0) for p in plans), 2),
        "done_count": by_status.get(2, 0),
        "rejected_count": by_status.get(3, 0),
        "pending_count": by_status.get(0, 0) + by_status.get(1, 0),
        "done_ratio": round(by_status.get(2, 0) / len(orders) * 100, 2) if orders else 0.0,
        "by_status": [
            {"status": key, "status_text": STATUS_TEXT.get(key, "未知"), "count": value}
            for key, value in sorted(by_status.items())
        ],
        "by_strategy": [
            {**value, "expected_gain": round(value["expected_gain"], 2)}
            for value in by_strategy.values()
        ],
        "daily": sorted(daily.values(), key=lambda item: item["date"]),
    }
