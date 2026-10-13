"""调度决策引擎。

决策流程
--------
1. **需求估计**：对目标日期/时段，按「区域 × 星期 × 小时」用近若干周历史均值
   并做近期趋势修正，得到各区域预测需求量（轻量级季节周期模型，
   与「需求预测」模块同源；需要逐时精细预测时使用预测模块的多元回归等模型）。
2. **运力盘点**：以车辆常驻区域为口径统计可用运力，扣除已下发未执行的调度车辆，
   再按单车小时服务能力折算为可承接订单数。
3. **供需缺口**：``缺口 = 预测需求 - 折算运力``，正值为缺口区域，负值为盈余区域。
4. **调度指派**：把盈余区域的车辆指派到缺口区域。同一区域每多调入一辆车，
   边际收益递减（可承接的缺口越来越少），因此这是一个典型的
   **最大权匹配（指派）问题**，本模块同时实现两种求解策略并对比：

   * ``greedy``    贪心策略：每次选取净收益最大的「车辆-目标区域」组合（基线）
   * ``hungarian`` 匈牙利算法：在全局上求总净收益最大的最优指派（O(n³)）

   净收益 = 预期订单收入 − 调度成本（距离 × 单位里程成本）。

5. **效果评估**：对已执行完毕的调度单，用目标区域目标时段的真实收入
   与「同星期同时段历史基线」对比，得到实际增收并与预期值比较。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..core.sqlutil import as_float, datetime_bounds

# --------------------------------------------------------------------------
# 几何工具
# --------------------------------------------------------------------------


def haversine_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """两点球面距离（公里）。"""
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def road_distance_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """直线距离按绕行系数折算为实际行驶距离。"""
    return haversine_km(lng1, lat1, lng2, lat2) * settings.DISPATCH_DISTANCE_FACTOR


# --------------------------------------------------------------------------
# 匈牙利算法（最大权指派，最小费用流的 O(n³) 实现）
# --------------------------------------------------------------------------


def hungarian_max_weight(weights: Sequence[Sequence[float]]) -> List[Tuple[int, int]]:
    """求解最大权二分匹配（允许留空，即「任意基数」最大权匹配）。

    实现要点：净收益 ≤ 0 的组合一律裁剪为 0（业务含义就是「不调度」）。
    由于裁剪后所有权值非负，把矩阵补成 ``max(n, m)`` 阶方阵、
    补齐项权值取 0 后，最大权 *完美* 匹配与最大权 *任意基数* 匹配等价。

    :param weights: 收益矩阵（行=车辆，列=目标槽位），可为矩形或 numpy 数组
    :return: [(行下标, 列下标), ...]，仅返回收益 > 0 的匹配
    """
    if weights is None or len(weights) == 0:
        return []
    rows = [list(map(float, row)) for row in weights]
    if not rows or len(rows[0]) == 0:
        return []
    n = len(rows)
    m = len(rows[0])

    profit = [[0.0 if v < 0 else v for v in row] for row in rows]
    max_w = max(max(row) for row in profit)
    if max_w <= 0:
        return []
    # 转成最小费用：cost = max_w - profit
    cost = [[max_w - v for v in row] for row in profit]

    size = max(n, m)
    inf = float("inf")
    # 补齐项权值为 0 → 费用为 max_w
    padded = [
        [cost[i][j] if (i < n and j < m) else max_w for j in range(size)]
        for i in range(size)
    ]

    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)

    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = inf
            j1 = -1
            for j in range(1, size + 1):
                if not used[j]:
                    cur = padded[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    result: List[Tuple[int, int]] = []
    for j in range(1, size + 1):
        i = p[j]
        if i and i <= n and j <= m and profit[i - 1][j - 1] > 0:
            result.append((i - 1, j - 1))
    return result


def greedy_assignment(weights: Sequence[Sequence[float]]) -> List[Tuple[int, int]]:
    """贪心指派（基线策略）：每次取当前最大收益组合。"""
    if weights is None or len(weights) == 0:
        return []
    n, m = len(weights), len(weights[0])
    if n == 0 or m == 0:
        return []
    candidates = [
        (float(weights[i][j]), i, j)
        for i in range(n)
        for j in range(m)
        if weights[i][j] > 0
    ]
    candidates.sort(reverse=True)
    used_rows, used_cols = set(), set()
    result = []
    for value, i, j in candidates:
        if i in used_rows or j in used_cols:
            continue
        used_rows.add(i)
        used_cols.add(j)
        result.append((i, j))
    return result


# --------------------------------------------------------------------------
# 需求估计 与 运力盘点
# --------------------------------------------------------------------------


def _trend_factor(db: Session, target_date: date) -> float:
    """近期趋势修正系数：近 7 天需求 / 前 7 天需求，限制在 [0.7, 1.4]。"""
    recent_lo = datetime.combine(target_date - timedelta(days=7), dtime.min)
    recent_hi = datetime.combine(target_date, dtime.min)
    older_lo = datetime.combine(target_date - timedelta(days=14), dtime.min)
    recent_total = (
        db.query(func.count(models.RideRequest.id))
        .filter(
            models.RideRequest.request_time >= recent_lo,
            models.RideRequest.request_time < recent_hi,
        )
        .scalar()
        or 0
    )
    older_total = (
        db.query(func.count(models.RideRequest.id))
        .filter(
            models.RideRequest.request_time >= older_lo,
            models.RideRequest.request_time < recent_lo,
        )
        .scalar()
        or 0
    )
    if older_total <= 0:
        return 1.0
    return float(np.clip(recent_total / older_total, 0.7, 1.4))


def estimate_day_demand(
    db: Session, target_date: date, lookback_weeks: int = 4
) -> Tuple[Dict[int, Dict[int, float]], str]:
    """一次算出目标日期 24 个小时、各区域的预测需求。

    :return: ({hour: {region_id: demand}}, 方法说明)
    """
    end = target_date - timedelta(days=1)
    start = end - timedelta(days=lookback_weeks * 7 + 6)
    lo, hi = datetime_bounds(start, end)

    inner = (
        db.query(
            models.RideRequest.region_id.label("region_id"),
            models.RideRequest.weekday.label("weekday"),
            models.RideRequest.hour.label("hour"),
            models.RideRequest.stat_date.label("stat_date"),
            func.count(models.RideRequest.id).label("cnt"),
        )
        .filter(models.RideRequest.request_time >= lo, models.RideRequest.request_time <= hi)
        .group_by(
            models.RideRequest.region_id,
            models.RideRequest.weekday,
            models.RideRequest.hour,
            models.RideRequest.stat_date,
        )
        .subquery()
    )
    rows = (
        db.query(inner.c.region_id, inner.c.hour, func.avg(inner.c.cnt))
        .filter(inner.c.weekday == target_date.weekday())
        .group_by(inner.c.region_id, inner.c.hour)
        .all()
    )
    factor = _trend_factor(db, target_date)
    result: Dict[int, Dict[int, float]] = {hour: {} for hour in range(24)}
    for region_id, hour, value in rows:
        result[int(hour)][int(region_id)] = max(0.0, float(value or 0) * factor)
    method = f"季节周期均值(近{lookback_weeks}周同星期同时段) × 趋势修正 {factor:.3f}"
    return result, method


def estimate_hourly_demand(
    db: Session,
    target_date: date,
    target_hour: int,
    lookback_weeks: int = 4,
) -> Tuple[Dict[int, float], str]:
    """估计各区域在目标「星期 × 小时」上的需求量。"""
    day_demand, method = estimate_day_demand(db, target_date, lookback_weeks)
    return day_demand.get(int(target_hour), {}), method


def region_avg_amount(db: Session, days: int = 30) -> Dict[int, float]:
    """近若干天各区域的平均订单金额（用于估算调度增收）。"""
    since = datetime.now() - timedelta(days=days)
    rows = (
        db.query(
            models.OperationRecord.pickup_region_id,
            func.avg(models.OperationRecord.amount),
        )
        .filter(models.OperationRecord.start_time >= since)
        .group_by(models.OperationRecord.pickup_region_id)
        .all()
    )
    return {int(r[0]): float(r[1] or 0) for r in rows if r[0] is not None}


def current_supply(
    db: Session, target_hour: int, plan_date: date
) -> Tuple[Dict[int, int], Dict[int, int]]:
    """统计各区域当前可用运力（以车辆常驻区域为口径），并扣除已调度未执行的车辆。"""
    rows = (
        db.query(models.Vehicle.home_region_id, func.count(models.Vehicle.id))
        .filter(models.Vehicle.status == 1, models.Vehicle.home_region_id.isnot(None))
        .group_by(models.Vehicle.home_region_id)
        .all()
    )
    supply = {int(r[0]): int(r[1]) for r in rows}

    # 已下发但未执行的调度车辆占用的运力
    pending = (
        db.query(models.DispatchOrder.to_region_id, func.count(models.DispatchOrder.id))
        .join(models.DispatchPlan, models.DispatchPlan.id == models.DispatchOrder.plan_id)
        .filter(
            models.DispatchPlan.plan_date == plan_date,
            models.DispatchOrder.status.in_((0, 1)),
            models.DispatchOrder.start_hour <= target_hour,
            models.DispatchOrder.end_hour > target_hour,
        )
        .group_by(models.DispatchOrder.to_region_id)
        .all()
    )
    occupied = {int(r[0]): int(r[1]) for r in pending}
    return supply, occupied


# --------------------------------------------------------------------------
# 核心：生成调度方案
# --------------------------------------------------------------------------


@dataclass
class RegionState:
    """区域供需状态。"""

    region_id: int
    region_name: str
    region_type: str
    lng: float
    lat: float
    predicted_demand: float
    current_supply: int
    occupied: int = 0
    avg_amount: float = 20.0
    effective_supply: float = 0.0
    gap: float = 0.0
    gap_level: str = "平衡"
    movable_out: int = 0
    needed_in: int = 0

    def to_dict(self) -> Dict:
        return {
            "region_id": self.region_id,
            "region_name": self.region_name,
            "region_type": self.region_type,
            "predicted_demand": round(self.predicted_demand, 2),
            "current_supply": self.current_supply,
            "effective_supply": round(self.effective_supply, 2),
            "gap": round(self.gap, 2),
            "gap_level": self.gap_level,
            "expected_revenue": round(
                min(max(self.gap, 0.0), self.needed_in * settings.VEHICLE_SERVICE_RATE)
                * self.avg_amount,
                2,
            ),
        }


def _gap_level(gap: float, demand: float) -> str:
    if gap <= 0:
        return "运力盈余"
    ratio = gap / max(demand, 1e-6)
    if ratio >= 0.4:
        return "严重缺口"
    if ratio >= 0.15:
        return "明显缺口"
    return "轻微缺口"


def _gap_balance(demand: Dict[int, float], supply_map: Dict[int, int]) -> Tuple[float, float, float]:
    """计算某时段的缺口、盈余与「可再分配量」。

    可再分配量 = min(总缺口, 总盈余)，代表跨区调度在该时段最多能缓解多少需求。
    :return: (总缺口, 总盈余, 可再分配量)
    """
    deficit = 0.0
    surplus = 0.0
    rate = settings.VEHICLE_SERVICE_RATE
    for region_id, value in demand.items():
        capacity = supply_map.get(region_id, 0) * rate
        diff = value - capacity
        if diff > 0:
            deficit += diff
        else:
            surplus += -diff
    return deficit, surplus, min(deficit, surplus)


def peak_hour_in_day(
    db: Session, target_date: date, earliest_hour: int = 0
) -> Tuple[int, str]:
    """在指定日期内挑选最适合调度的时段（可再分配量最大）。"""
    day_demand, method = estimate_day_demand(db, target_date)
    supply_map, _ = current_supply(db, target_hour=0, plan_date=target_date)
    best_hour = max(0, min(23, earliest_hour))
    best_score = (-1.0, -1.0)
    for hour in range(max(0, min(23, earliest_hour)), 24):
        deficit, surplus, movable = _gap_balance(day_demand.get(hour, {}), supply_map)
        score = (movable, deficit)
        if score > best_score:
            best_score, best_hour = score, hour
    return int(best_hour), method


def pick_peak_hour(
    db: Session, start: Optional[datetime] = None, horizon_hours: int = 24
) -> Tuple[date, int, str]:
    """在「未来 ``horizon_hours`` 小时」范围内挑选最适合调度的时段。

    评价标准是**可再分配量** = min(总缺口, 总盈余)，而不是单纯的缺口大小：
    全城普遍缺车时并没有运力可以调过去，真正值得调度的是
    「一部分区域缺、另一部分区域富余」的时段。
    """
    start = start or datetime.now()
    cache: Dict[date, Tuple[Dict[int, Dict[int, float]], str]] = {}
    best_day = start.date()
    best_hour = (start.hour + 1) % 24
    best_score = (-1.0, -1.0)
    method = ""
    for offset in range(1, horizon_hours + 1):
        moment = start + timedelta(hours=offset)
        day = moment.date()
        if day not in cache:
            cache[day] = estimate_day_demand(db, day)
        day_demand, method = cache[day]
        supply_map, _ = current_supply(db, target_hour=moment.hour, plan_date=day)
        deficit, surplus, movable = _gap_balance(day_demand.get(moment.hour, {}), supply_map)
        score = (movable, deficit)
        if score > best_score:
            best_score, best_day, best_hour = score, day, moment.hour
    return best_day, int(best_hour), method


def _states_from_maps(
    regions: List[models.Region],
    demand_map: Dict[int, float],
    supply_map: Dict[int, int],
    occupied_map: Dict[int, int],
    amount_map: Dict[int, float],
) -> List[RegionState]:
    """由供需字典构建区域状态列表（供单时段与多时段批量计算复用）。"""
    global_amount = float(np.mean(list(amount_map.values()))) if amount_map else 20.0
    states: List[RegionState] = []
    for region in regions:
        demand = demand_map.get(region.id, 0.0)
        occupied = occupied_map.get(region.id, 0)
        available = max(0, supply_map.get(region.id, 0) - occupied)
        effective = available * settings.VEHICLE_SERVICE_RATE
        gap = demand - effective
        movable_out = 0
        needed_in = 0
        if gap < 0:
            movable_out = min(
                int(math.floor(-gap / max(settings.VEHICLE_SERVICE_RATE, 1e-6))),
                settings.DISPATCH_MAX_MOVE_OUT,
            )
        elif gap > 0:
            needed_in = min(
                int(math.ceil(gap / max(settings.VEHICLE_SERVICE_RATE, 1e-6))),
                settings.DISPATCH_MAX_MOVE_PER_REGION,
            )
        states.append(
            RegionState(
                region_id=region.id,
                region_name=region.name,
                region_type=region.region_type or "居民区",
                lng=as_float(region.center_lng, 0.0),
                lat=as_float(region.center_lat, 0.0),
                predicted_demand=demand,
                current_supply=available,
                occupied=occupied,
                avg_amount=amount_map.get(region.id, global_amount),
                effective_supply=effective,
                gap=gap,
                gap_level=_gap_level(gap, demand),
                movable_out=movable_out,
                needed_in=needed_in,
            )
        )
    return states


def build_region_states(
    db: Session,
    target_date: date,
    target_hour: int,
) -> Tuple[List[RegionState], str]:
    """构建各区域的供需状态列表。"""
    regions = db.query(models.Region).filter(models.Region.status == 1).all()
    if not regions:
        raise ValueError("尚未配置运营区域，请先维护区域信息")

    demand_map, method = estimate_hourly_demand(db, target_date, target_hour)
    supply_map, occupied_map = current_supply(db, target_hour, target_date)
    amount_map = region_avg_amount(db)
    return (
        _states_from_maps(regions, demand_map, supply_map, occupied_map, amount_map),
        method,
    )


def _build_slots(states: List[RegionState]) -> List[Tuple[int, float, float]]:
    """把缺口区域拆成「单车槽位」。

    第 k 辆调入车辆的边际收益递减：它能承接的订单数
    = min(单车服务能力, 该区域剩余缺口)。
    :return: [(区域下标, 该槽位可承接订单数, 预期收入), ...]
    """
    slots: List[Tuple[int, float, float]] = []
    for idx, state in enumerate(states):
        if state.needed_in <= 0 or state.gap <= 0:
            continue
        remaining = state.gap
        for _ in range(state.needed_in):
            orders = min(settings.VEHICLE_SERVICE_RATE, remaining)
            if orders <= 1e-6:
                break
            revenue = orders * state.avg_amount
            slots.append((idx, orders, revenue))
            remaining -= orders
    return slots


def _surplus_vehicles(
    db: Session, states: List[RegionState]
) -> List[Tuple[int, int, float, float]]:
    """取出可调度车辆。

    :return: [(车辆下标, 常驻区域下标, 经度, 纬度), ...]
    """
    surplus_idx = {s.region_id: i for i, s in enumerate(states)}
    quota: Dict[int, int] = {
        i: s.movable_out for i, s in enumerate(states) if s.movable_out > 0
    }
    if not quota:
        return []
    region_ids = [states[i].region_id for i in quota]

    vehicles = (
        db.query(models.Vehicle)
        .filter(
            models.Vehicle.status == 1,
            models.Vehicle.home_region_id.in_(region_ids),
        )
        .order_by(models.Vehicle.id)
        .all()
    )
    result: List[Tuple[int, int, float, float]] = []
    used: Dict[int, int] = {}
    for vehicle in vehicles:
        region_idx = surplus_idx.get(vehicle.home_region_id)
        if region_idx is None or region_idx not in quota:
            continue
        if used.get(region_idx, 0) >= quota[region_idx]:
            continue
        used[region_idx] = used.get(region_idx, 0) + 1
        state = states[region_idx]
        result.append((vehicle.id, region_idx, state.lng, state.lat))
    return result


def build_gain_matrix(
    states: List[RegionState],
    vehicles: List[Tuple[int, int, float, float]],
) -> Tuple[np.ndarray, List[Tuple[int, float, float]], List[Dict]]:
    """构造「车辆 × 槽位」的净收益矩阵，并记录成本明细。"""
    slots = _build_slots(states)
    if not vehicles or not slots:
        return np.zeros((0, 0)), slots, []

    matrix = np.zeros((len(vehicles), len(slots)))
    detail: List[Dict] = []
    for i, (vehicle_id, from_idx, lng, lat) in enumerate(vehicles):
        from_state = states[from_idx]
        for j, (to_idx, orders, revenue) in enumerate(slots):
            to_state = states[to_idx]
            distance = road_distance_km(lng, lat, to_state.lng, to_state.lat)
            cost = distance * settings.DISPATCH_COST_PER_KM
            gain = revenue - cost
            matrix[i, j] = gain
            if gain > settings.DISPATCH_MIN_NET_GAIN:
                detail.append(
                    {
                        "vehicle_id": vehicle_id,
                        "from_idx": from_idx,
                        "to_idx": to_idx,
                        "slot": j,
                        "orders": orders,
                        "revenue": revenue,
                        "distance_km": round(distance, 2),
                        "cost": round(cost, 2),
                        "gain": round(gain, 2),
                    }
                )
    return matrix, slots, detail


def solve_assignment(matrix: np.ndarray, strategy: str) -> List[Tuple[int, int]]:
    """按策略求解指派问题。"""
    if matrix.size == 0:
        return []
    if strategy == "greedy":
        return greedy_assignment(matrix)
    return hungarian_max_weight(matrix)


def generate_dispatch_plan(
    db: Session,
    plan_date: Optional[date] = None,
    target_hour: Optional[int] = None,
    strategy: str = "hungarian",
    auto_save: bool = True,
    created_by: Optional[str] = None,
) -> Dict:
    """生成调度方案（含区域供需状态与两种策略的对比）。"""
    now = datetime.now()
    auto_hour = target_hour is None
    if auto_hour:
        if plan_date is None:
            # 未指定日期与时段：自动选择未来 24 小时内缺口最大的时段
            plan_date, target_hour, picked_method = pick_peak_hour(db, now)
            auto_method = picked_method
        else:
            earliest = now.hour + 1 if plan_date == now.date() else 0
            target_hour, auto_method = peak_hour_in_day(db, plan_date, earliest)
    else:
        if plan_date is None:
            plan_date = now.date() + timedelta(days=1 if now.hour >= 23 else 0)
        auto_method = ""
    target_hour = int(target_hour)

    states, method = build_region_states(db, plan_date, target_hour)
    vehicles = _surplus_vehicles(db, states)
    matrix, slots, detail = build_gain_matrix(states, vehicles)

    warnings: List[str] = []
    if auto_hour:
        warnings.append(
            f"未指定目标时段，已自动选择缺口最大的时段："
            f"{plan_date.isoformat()} {target_hour:02d}:00-{(target_hour + 1) % 24:02d}:00"
        )
    deficit = [s for s in states if s.gap > 0]
    surplus = [s for s in states if s.movable_out > 0]
    if not deficit:
        warnings.append("目标时段各区域运力均能满足预测需求，无需调度")
    if not surplus:
        warnings.append("目标时段没有可调出的盈余运力，建议延长运营时间或调整排班")
    if deficit and not surplus:
        warnings.append("存在缺口但无可调运力，属于运力总量不足，需要增加运力投放")

    # 两种策略对比
    strategy_compare = []
    for name, label in (("greedy", "贪心策略"), ("hungarian", "匈牙利最优指派")):
        pairs = solve_assignment(matrix, name)
        total = float(sum(matrix[i][j] for i, j in pairs))
        strategy_compare.append(
            {
                "strategy": name,
                "strategy_label": label,
                "dispatch_count": len(pairs),
                "expected_gain": round(total, 2),
            }
        )

    pairs = solve_assignment(matrix, strategy)
    chosen = strategy_compare[0] if strategy == "greedy" else strategy_compare[1]
    if strategy not in ("greedy", "hungarian"):
        warnings.append(f"未知策略 {strategy}，已回退为匈牙利最优指派")
        strategy = "hungarian"
        chosen = strategy_compare[1]

    # 组装调度指令
    plan_no = f"DP{plan_date.strftime('%Y%m%d')}{target_hour:02d}{np.random.randint(100, 999)}"
    order_payloads = []
    detail_index = {(d["vehicle_id"], d["slot"]): d for d in detail}
    for i, j in pairs:
        vehicle_id, from_idx, _, _ = vehicles[i]
        to_idx, orders, revenue = slots[j]
        info = detail_index.get((vehicle_id, j))
        if info is None:
            continue
        from_state, to_state = states[from_idx], states[to_idx]
        order_payloads.append(
            {
                "id": None,
                "plan_id": None,
                "dispatch_no": f"{plan_no}-{len(order_payloads) + 1:03d}",
                "vehicle_id": vehicle_id,
                "driver_id": None,
                "from_region_id": from_state.region_id,
                "to_region_id": to_state.region_id,
                "start_hour": target_hour,
                "end_hour": (target_hour + 1) % 24,
                "predicted_demand": round(to_state.predicted_demand, 2),
                "predicted_supply": round(to_state.effective_supply, 2),
                "gap": round(to_state.gap, 2),
                "distance_km": info["distance_km"],
                "expected_revenue": round(info["revenue"], 2),
                "expected_cost": round(info["cost"], 2),
                "expected_gain": round(info["gain"], 2),
                "priority": (
                    1 if to_state.gap_level == "严重缺口"
                    else 2 if to_state.gap_level == "明显缺口"
                    else 3
                ),
                "status": 0,
                "from_region_name": from_state.region_name,
                "to_region_name": to_state.region_name,
            }
        )
    order_payloads.sort(key=lambda item: (item["priority"], -item["expected_gain"]))
    for index, item in enumerate(order_payloads):
        item["dispatch_no"] = f"{plan_no}-{index + 1:03d}"

    total_demand = sum(s.predicted_demand for s in states)
    total_supply = sum(s.effective_supply for s in states)
    total_gap = sum(max(s.gap, 0.0) for s in states)
    expected_gain = round(sum(o["expected_gain"] for o in order_payloads), 2)

    plan_payload = {
        "id": None,
        "plan_no": plan_no,
        "plan_date": plan_date,
        "target_hour": target_hour,
        "strategy": strategy,
        "forecast_model": method,
        "total_demand": round(total_demand, 2),
        "total_supply": round(total_supply, 2),
        "total_gap": round(total_gap, 2),
        "dispatch_count": len(order_payloads),
        "expected_gain": expected_gain,
        "status": 0,
        "remark": (
            f"目标时段 {target_hour:02d}:00-{(target_hour + 1) % 24:02d}:00，"
            f"需求估计方法：{method}，调度策略：{chosen['strategy_label']}"
        ),
        "created_by": created_by,
        "orders": order_payloads,
    }

    saved = None
    if auto_save and order_payloads:
        saved = save_plan(db, plan_payload)
        plan_payload["id"] = saved.id

    return {
        "plan": plan_payload,
        "region_status": [s.to_dict() for s in states],
        "strategy_compare": strategy_compare,
        "warnings": warnings,
        "saved": saved is not None,
        "detail": detail,
    }


def save_plan(db: Session, payload: Dict) -> models.DispatchPlan:
    """持久化调度方案与调度指令。"""
    plan = models.DispatchPlan(
        plan_no=payload["plan_no"],
        plan_date=payload["plan_date"],
        target_hour=payload["target_hour"],
        strategy=payload["strategy"],
        forecast_model=payload.get("forecast_model"),
        total_demand=payload.get("total_demand", 0),
        total_supply=payload.get("total_supply", 0),
        total_gap=payload.get("total_gap", 0),
        dispatch_count=payload.get("dispatch_count", 0),
        expected_gain=payload.get("expected_gain", 0),
        status=payload.get("status", 0),
        remark=payload.get("remark"),
        created_by=payload.get("created_by"),
    )
    db.add(plan)
    db.flush()

    # 为调度车辆匹配当前绑定驾驶员
    vehicle_ids = [o["vehicle_id"] for o in payload["orders"]]
    driver_map: Dict[int, int] = {}
    if vehicle_ids:
        bindings = (
            db.query(models.VehicleDriver)
            .filter(
                models.VehicleDriver.vehicle_id.in_(vehicle_ids),
                models.VehicleDriver.status == 1,
            )
            .all()
        )
        for binding in bindings:
            driver_map.setdefault(binding.vehicle_id, binding.driver_id)

    for index, item in enumerate(payload["orders"]):
        db.add(
            models.DispatchOrder(
                plan_id=plan.id,
                dispatch_no=f"{payload['plan_no']}-{index + 1:03d}",
                vehicle_id=item["vehicle_id"],
                driver_id=driver_map.get(item["vehicle_id"]),
                from_region_id=item["from_region_id"],
                to_region_id=item["to_region_id"],
                start_hour=item["start_hour"],
                end_hour=item["end_hour"],
                predicted_demand=item["predicted_demand"],
                predicted_supply=item["predicted_supply"],
                gap=item["gap"],
                distance_km=item["distance_km"],
                expected_revenue=item["expected_revenue"],
                expected_cost=item["expected_cost"],
                expected_gain=item["expected_gain"],
                priority=item["priority"],
                status=0,
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


# --------------------------------------------------------------------------
# 策略对比实验：贪心 vs 匈牙利
# --------------------------------------------------------------------------


def compare_strategies(
    db: Session, start: Optional[datetime] = None, hours: int = 24
) -> Dict:
    """在未来 ``hours`` 个整点上分别用两种策略求解，对比总体调度效果。

    这是论文中「调度算法对比实验」的数据来源：单一时段的算例规模较小，
    贪心与最优解常常相同；在连续多个时段上做批量对比才能体现算法差异。
    """
    start = start or datetime.now()
    regions = db.query(models.Region).filter(models.Region.status == 1).all()
    if not regions:
        raise ValueError("尚未配置运营区域，请先维护区域信息")
    amount_map = region_avg_amount(db)

    demand_cache: Dict[date, Dict[int, Dict[int, float]]] = {}
    rows: List[Dict] = []
    totals = {
        "greedy": {"dispatch_count": 0, "expected_gain": 0.0},
        "hungarian": {"dispatch_count": 0, "expected_gain": 0.0},
    }
    better_hours = 0
    tie_hours = 0
    evaluated_hours = 0

    for offset in range(1, max(1, hours) + 1):
        moment = start + timedelta(hours=offset)
        day = moment.date()
        if day not in demand_cache:
            demand_cache[day] = estimate_day_demand(db, day)[0]
        supply_map, occupied_map = current_supply(db, moment.hour, day)
        states = _states_from_maps(
            regions, demand_cache[day].get(moment.hour, {}), supply_map, occupied_map, amount_map
        )
        vehicles = _surplus_vehicles(db, states)
        matrix, slots, _ = build_gain_matrix(states, vehicles)
        if matrix.size == 0:
            continue
        evaluated_hours += 1
        greedy_pairs = solve_assignment(matrix, "greedy")
        hungarian_pairs = solve_assignment(matrix, "hungarian")
        greedy_gain = float(sum(matrix[i][j] for i, j in greedy_pairs))
        hungarian_gain = float(sum(matrix[i][j] for i, j in hungarian_pairs))
        totals["greedy"]["dispatch_count"] += len(greedy_pairs)
        totals["greedy"]["expected_gain"] += greedy_gain
        totals["hungarian"]["dispatch_count"] += len(hungarian_pairs)
        totals["hungarian"]["expected_gain"] += hungarian_gain
        if hungarian_gain > greedy_gain + 1e-9:
            better_hours += 1
        elif abs(hungarian_gain - greedy_gain) <= 1e-9:
            tie_hours += 1
        rows.append(
            {
                "time": moment.replace(minute=0, second=0, microsecond=0),
                "hour": moment.hour,
                "deficit_regions": sum(1 for s in states if s.gap > 0),
                "surplus_regions": sum(1 for s in states if s.movable_out > 0),
                "total_gap": round(sum(max(s.gap, 0.0) for s in states), 2),
                "greedy_count": len(greedy_pairs),
                "greedy_gain": round(greedy_gain, 2),
                "hungarian_count": len(hungarian_pairs),
                "hungarian_gain": round(hungarian_gain, 2),
                "improve": round(hungarian_gain - greedy_gain, 2),
                "improve_pct": (
                    round((hungarian_gain - greedy_gain) / greedy_gain * 100, 2)
                    if greedy_gain > 1e-9
                    else None
                ),
            }
        )

    greedy_total = totals["greedy"]["expected_gain"]
    hungarian_total = totals["hungarian"]["expected_gain"]
    return {
        "hours": hours,
        "evaluated_hours": evaluated_hours,
        "start": start,
        "rows": rows,
        "totals": {
            "greedy": {**totals["greedy"], "expected_gain": round(greedy_total, 2)},
            "hungarian": {**totals["hungarian"], "expected_gain": round(hungarian_total, 2)},
        },
        "improve": round(hungarian_total - greedy_total, 2),
        "improve_pct": (
            round((hungarian_total - greedy_total) / greedy_total * 100, 2)
            if greedy_total > 1e-9
            else None
        ),
        "better_hours": better_hours,
        "tie_hours": tie_hours,
    }


# --------------------------------------------------------------------------
# 算法基准实验：不同规模随机算例下的贪心 vs 匈牙利
# --------------------------------------------------------------------------


def benchmark_assignment(
    n_instances: int = 200,
    sizes: Optional[Sequence[int]] = None,
    seed: int = 20240501,
) -> Dict:
    """在随机算例上对比两种指派策略的解质量与耗时。

    收益矩阵按调度问题的真实结构生成：``收益(i, j) = 订单收入(j) − 距离成本(i, j)``，
    其中收入随槽位递减（同一区域每多调入一辆车，边际收益下降），
    距离成本由随机坐标计算得到。

    :return: 每个规模下的对比结果
    """
    import time as _time

    sizes = list(sizes) if sizes else [4, 8, 12, 20, 30, 40]
    rng = np.random.default_rng(seed)
    output = []

    for size in sizes:
        greedy_gains: List[float] = []
        hungarian_gains: List[float] = []
        better = ties = 0
        greedy_ms = hungarian_ms = 0.0

        for _ in range(n_instances):
            # 经纬度偏移量（±0.055° ≈ ±6 公里），保证算例规模贴近城市内部调度
            coords = rng.uniform(-0.055, 0.055, size=(2 * size, 2))
            # 槽位收入：递减的边际收益
            base_revenue = np.sort(rng.uniform(20, 60, size=size))[::-1]
            revenue = base_revenue * rng.uniform(0.9, 1.0, size=size)
            matrix = np.zeros((size, size))
            for i in range(size):
                for j in range(size):
                    d = haversine_km(
                        coords[i][0], coords[i][1], coords[size + j][0], coords[size + j][1]
                    )
                    matrix[i][j] = revenue[j] - d * settings.DISPATCH_COST_PER_KM

            start = _time.perf_counter()
            g_pairs = greedy_assignment(matrix)
            greedy_ms += (_time.perf_counter() - start) * 1000

            start = _time.perf_counter()
            h_pairs = hungarian_max_weight(matrix)
            hungarian_ms += (_time.perf_counter() - start) * 1000

            g_gain = float(sum(matrix[i][j] for i, j in g_pairs))
            h_gain = float(sum(matrix[i][j] for i, j in h_pairs))
            greedy_gains.append(g_gain)
            hungarian_gains.append(h_gain)
            if h_gain > g_gain + 1e-9:
                better += 1
            elif abs(h_gain - g_gain) <= 1e-9:
                ties += 1

        mean_greedy = float(np.mean(greedy_gains))
        mean_hungarian = float(np.mean(hungarian_gains))
        output.append(
            {
                "size": size,
                "instances": n_instances,
                "greedy_mean_gain": round(mean_greedy, 2),
                "hungarian_mean_gain": round(mean_hungarian, 2),
                "mean_improve": round(mean_hungarian - mean_greedy, 2),
                "improve_pct": (
                    round((mean_hungarian - mean_greedy) / mean_greedy * 100, 3)
                    if mean_greedy > 1e-9
                    else None
                ),
                "hungarian_better_instances": better,
                "tie_instances": ties,
                "better_ratio": round(better / n_instances * 100, 1),
                "greedy_avg_ms": round(greedy_ms / n_instances, 3),
                "hungarian_avg_ms": round(hungarian_ms / n_instances, 3),
            }
        )
    return {
        "seed": seed,
        "cost_per_km": settings.DISPATCH_COST_PER_KM,
        "results": output,
    }


# --------------------------------------------------------------------------
# 调度效果评估
# --------------------------------------------------------------------------


def evaluate_plan(db: Session, plan_id: int) -> Dict:
    """评估调度方案的实际执行效果。

    对每条已完成/执行中的调度单，计算目标区域目标时段的真实收入，
    与「前 3 周同星期同时段平均收入」基线对比得到实际增收。
    """
    plan = db.get(models.DispatchPlan, plan_id)
    if not plan:
        raise ValueError("调度方案不存在")

    orders = (
        db.query(models.DispatchOrder)
        .filter(models.DispatchOrder.plan_id == plan_id)
        .all()
    )
    detail = []
    actual_gain = 0.0
    done_count = 0

    for order in orders:
        if order.status in (2, 1):
            done_count += 1
        start = datetime.combine(plan.plan_date, dtime(hour=int(order.start_hour)))
        end = start + timedelta(hours=1)
        actual = (
            db.query(func.coalesce(func.sum(models.OperationRecord.amount), 0))
            .filter(
                models.OperationRecord.pickup_region_id == order.to_region_id,
                models.OperationRecord.start_time >= start,
                models.OperationRecord.start_time < end,
            )
            .scalar()
            or 0
        )

        # 基线：前 3 周同星期同时段的平均收入
        baselines = []
        for week in range(1, 4):
            day = plan.plan_date - timedelta(days=7 * week)
            b_start = datetime.combine(day, dtime(hour=int(order.start_hour)))
            b_end = b_start + timedelta(hours=1)
            value = (
                db.query(func.coalesce(func.sum(models.OperationRecord.amount), 0))
                .filter(
                    models.OperationRecord.pickup_region_id == order.to_region_id,
                    models.OperationRecord.start_time >= b_start,
                    models.OperationRecord.start_time < b_end,
                )
                .scalar()
                or 0
            )
            baselines.append(float(value))
        baseline = float(np.mean(baselines)) if baselines else 0.0
        cost = float(order.expected_cost or 0)
        # 按该区域当次调度车辆数分摊增量收入
        share = 1.0 / max(1, sum(1 for o in orders if o.to_region_id == order.to_region_id))
        uplift = (float(actual) - baseline) * share - cost

        if order.status == 2:
            actual_gain += uplift
        detail.append(
            {
                "dispatch_no": order.dispatch_no,
                "to_region_id": order.to_region_id,
                "to_region_name": order.to_region.name if order.to_region else None,
                "status": order.status,
                "expected_gain": float(order.expected_gain or 0),
                "actual_income": round(float(actual), 2),
                "baseline_income": round(baseline, 2),
                "actual_gain": round(uplift, 2),
                "distance_km": float(order.distance_km or 0),
            }
        )

    expected = float(plan.expected_gain or 0)
    accuracy = None
    if expected > 0 and done_count > 0:
        accuracy = round(max(0.0, 100 - abs(actual_gain - expected * done_count / max(len(orders), 1))
                             / max(expected, 1e-6) * 100), 2)
    return {
        "plan_id": plan.id,
        "plan_no": plan.plan_no,
        "dispatch_count": len(orders),
        "done_count": done_count,
        "done_ratio": round(done_count / max(len(orders), 1) * 100, 2),
        "expected_gain": expected,
        "actual_gain": round(actual_gain, 2),
        "accuracy": accuracy,
        "detail": detail,
    }
