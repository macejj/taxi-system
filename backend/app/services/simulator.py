"""运营数据仿真生成器。

用途
----
生成一套**可复现、有业务规律**的出租车运营数据，用于系统演示与需求预测建模：

* 10 个功能区（交通枢纽、商圈、居民区、大学城、景区、医院、工业区等）
* 60 台营运车辆、80 名驾驶员、人车绑定与班次排班
* 逐小时「叫车需求」泊松过程，含：

  - 日周期（早晚高峰）
  - 周周期（工作日 / 周末差异）
  - 趋势（缓慢增长）
  - 天气因子（雨天需求上升）
  - 节假日因子
  - 区域差异（功能区需求强度）

* 需求满足率随区域小时负荷变化 —— 高峰期出现「无人接单」，
  使供需缺口、调度决策模块有真实可分析的对象。

所有随机过程使用固定随机种子，结果可复现。
"""
from __future__ import annotations

import random
from datetime import date, datetime, time as dtime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy import delete
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..core.sqlutil import is_peak_hour
from .dispatch import haversine_km

# --------------------------------------------------------------------------
# 静态模板
# --------------------------------------------------------------------------

#: 区域模板：(编码, 名称, 功能区, 经度, 纬度, 面积km², 需求强度1-5)
#: 坐标集中在约 10km × 10km 的城区范围内，使行程距离与车费符合城市出租车实际水平
REGION_TEMPLATES: Sequence[Tuple[str, str, str, float, float, float, int]] = (
    ("R01", "火车站广场", "交通枢纽", 113.6500, 34.7550, 3.2, 5),
    ("R02", "二七商圈", "商圈", 113.6560, 34.7620, 4.1, 5),
    ("R03", "会展中心", "商圈", 113.6900, 34.7720, 5.6, 4),
    ("R04", "高新技术开发区", "工业区", 113.6100, 34.7900, 14.5, 3),
    ("R05", "大学城", "学校", 113.6180, 34.7960, 9.8, 4),
    ("R06", "滨河新城", "居民区", 113.6850, 34.7350, 12.4, 2),
    ("R07", "老城区", "居民区", 113.6420, 34.7680, 6.7, 3),
    ("R08", "国际机场", "交通枢纽", 113.7200, 34.7050, 8.9, 4),
    ("R09", "人民公园景区", "景区", 113.6350, 34.7760, 5.2, 3),
    ("R10", "市第一人民医院", "医院", 113.6650, 34.7480, 2.8, 3),
)

#: 功能区形态与城市小时曲线的混合权重（避免两者相乘造成过于极端的峰谷比）
TYPE_BLEND = 0.55
#: 目标平均运力负荷率：需求与运力之比，用于自动标定需求规模
TARGET_LOAD = 0.85

VEHICLE_BRANDS = (
    ("大众 捷达", "白色", "燃油"),
    ("大众 桑塔纳", "银色", "燃油"),
    ("丰田 卡罗拉", "白色", "混动"),
    ("丰田 凯美瑞", "黑色", "混动"),
    ("比亚迪 秦PLUS", "白色", "纯电"),
    ("比亚迪 e5", "蓝色", "纯电"),
    ("广汽埃安 AION S", "银色", "纯电"),
    ("现代 伊兰特", "白色", "燃油"),
    ("日产 轩逸", "黑色", "燃油"),
    ("吉利 帝豪", "灰色", "燃油"),
)

VEHICLE_TYPES = ("巡游出租车", "巡游出租车", "巡游出租车", "网约车")
PAY_TYPES = (("微信", 45), ("支付宝", 30), ("现金", 8), ("银行卡", 5), ("聚合支付", 12))
WEATHERS = (("晴", 62), ("阴", 20), ("雨", 13), ("雪", 3), ("雾", 2))
SHIFTS = ("白班", "夜班", "全天")

#: 小时需求系数（0-23 点），体现早晚高峰
HOUR_FACTOR = np.array(
    [
        0.28, 0.18, 0.13, 0.10, 0.12, 0.22,   # 0-5 深夜
        0.55, 1.35, 2.05, 1.62, 1.15, 1.05,   # 6-11 早高峰
        1.00, 0.95, 0.92, 0.98, 1.28, 2.10,   # 12-17 午后 + 晚高峰
        1.85, 1.52, 1.30, 1.05, 0.78, 0.45,   # 18-23 夜间
    ],
    dtype=float,
)

#: 星期需求系数（0=周一）
WEEKDAY_FACTOR = np.array([1.00, 1.02, 1.03, 1.05, 1.18, 1.15, 0.95], dtype=float)

#: 功能区的小时形态修正（乘性）。使用前会归一化到均值为 1，因此这里只表达「形状」。
#: 设计要点：不同功能区的出行高峰在时间上错开，
#: 使同一时刻既有运力紧张的区域、也有运力富余的区域，
#: 从而让「供需缺口分析 + 跨区调度」有真实可用的调度空间。
TYPE_HOUR_MODIFIER: Dict[str, np.ndarray] = {
    "交通枢纽": np.array(
        [1.6, 1.3, 1.0, 0.9, 1.1, 1.5, 1.9, 1.7, 1.4, 1.3, 1.2, 1.1,
         1.1, 1.1, 1.1, 1.2, 1.3, 1.5, 1.7, 1.7, 1.7, 1.8, 1.9, 1.8]
    ),
    "商圈": np.array(
        [0.90, 0.70, 0.50, 0.35, 0.30, 0.35, 0.50, 0.70, 0.90, 1.10, 1.30, 1.50,
         1.50, 1.40, 1.30, 1.40, 1.70, 2.10, 2.40, 2.40, 2.20, 1.90, 1.60, 1.20]
    ),
    "居民区": np.array(
        [1.30, 1.00, 0.70, 0.50, 0.50, 1.00, 1.70, 2.40, 2.20, 1.30, 0.90, 0.80,
         0.80, 0.80, 0.80, 0.90, 1.20, 1.70, 1.90, 1.60, 1.40, 1.30, 1.30, 1.30]
    ),
    "学校": np.array(
        [0.80, 0.50, 0.30, 0.20, 0.30, 0.70, 1.30, 2.00, 2.20, 1.50, 1.10, 1.00,
         1.00, 1.00, 0.90, 0.90, 1.20, 1.70, 1.90, 1.70, 1.50, 1.50, 1.40, 1.10]
    ),
    "景区": np.array(
        [0.40, 0.25, 0.15, 0.10, 0.15, 0.30, 0.70, 1.10, 1.70, 2.10, 2.30, 2.10,
         1.80, 1.80, 1.90, 2.00, 1.90, 1.50, 1.10, 0.90, 0.70, 0.60, 0.50, 0.45]
    ),
    "医院": np.array(
        [0.70, 0.50, 0.40, 0.30, 0.40, 0.70, 1.40, 2.00, 2.30, 2.00, 1.50, 1.20,
         1.10, 1.20, 1.30, 1.30, 1.10, 1.00, 0.90, 0.80, 0.80, 0.80, 0.80, 0.80]
    ),
    "工业区": np.array(
        [0.60, 0.40, 0.25, 0.20, 0.30, 0.80, 1.70, 2.40, 2.10, 1.30, 1.00, 0.90,
         0.90, 0.90, 0.90, 1.00, 1.50, 2.20, 2.30, 1.80, 1.40, 1.20, 0.90, 0.70]
    ),
}

HOLIDAY_MD = (
    (1, 1), (1, 2), (1, 3),
    (5, 1), (5, 2), (5, 3),
    (10, 1), (10, 2), (10, 3), (10, 4), (10, 5), (10, 6), (10, 7),
)

SURNAMES = tuple(
    "王李张刘陈杨黄赵周吴徐孙马朱胡郭何高林罗郑梁谢宋唐许韩冯邓曹彭曾肖田董袁潘于蒋"
    "蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯"
)
GIVEN_NAMES = (
    "伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "娟", "涛",
    "明", "超", "霞", "平", "刚", "建国", "志强", "建华", "文军", "晓东", "晓明", "海涛",
    "俊杰", "晓峰", "立新", "玉兰", "秀珍", "丹丹", "小燕", "国庆", "卫东", "春燕", "桂芳",
    "鹏", "宇", "浩", "鑫", "琳", "雪", "婷", "凯", "亮", "斌", "峰", "龙",
)


# --------------------------------------------------------------------------
# 辅助
# --------------------------------------------------------------------------


def weighted_choice(rng: random.Random, pairs: Sequence[Tuple[str, int]]) -> str:
    total = sum(weight for _, weight in pairs)
    point = rng.uniform(0, total)
    upto = 0.0
    for value, weight in pairs:
        upto += weight
        if point <= upto:
            return value
    return pairs[-1][0]


def is_holiday_date(day: date) -> bool:
    return (day.month, day.day) in HOLIDAY_MD


def shift_covers(shift: str, hour: int) -> bool:
    if shift == "白班":
        return 6 <= hour < 18
    if shift == "夜班":
        return hour >= 18 or hour < 6
    return True


# --------------------------------------------------------------------------
# 主生成器
# --------------------------------------------------------------------------


class DataSimulator:
    """运营数据仿真器。"""

    def __init__(self, db: Session, seed: int = 20240501, verbose: bool = True):
        self.db = db
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.verbose = verbose
        self.stats: Dict[str, int] = {}

    def log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    # ------------------------------------------------------------ 需求模型

    @staticmethod
    def effective_hour_factor(region_type: str) -> np.ndarray:
        """区域的有效小时需求系数。

        做法：先把功能区形态归一化到均值为 1（只保留「形状」信息），
        再与城市小时曲线做加权混合，最后乘回城市曲线：

            factor(h) = HOUR_FACTOR(h) × [1 + (shape(h) - 1) × TYPE_BLEND]

        这样城市整体的峰谷形态由 HOUR_FACTOR 决定，
        而区域之间的差异由归一化后的 shape 决定，两者互不干扰。
        """
        shape = TYPE_HOUR_MODIFIER.get(region_type)
        if shape is None:
            return HOUR_FACTOR.copy()
        shape = shape / shape.mean()
        return HOUR_FACTOR * (1.0 + (shape - 1.0) * TYPE_BLEND)

    def demand_share(self, regions: List[models.Region]) -> Dict[int, float]:
        """各区域的相对需求量（用于运力分配）。"""
        return {
            r.id: r.demand_level * float(self.effective_hour_factor(r.region_type or "居民区").mean())
            for r in regions
        }

    # ------------------------------------------------------------ 清库

    def reset(self, include_master: bool = True) -> None:
        """清空业务数据。

        :param include_master: 是否同时清空车辆/驾驶员/区域等基础档案
        """
        self.log("清空原有业务数据 ...")
        targets = [
            models.DispatchOrder,
            models.DispatchPlan,
            models.ForecastResult,
            models.OperationRecord,
            models.RideRequest,
            models.VehicleDriver,
        ]
        if include_master:
            targets += [models.Vehicle, models.Driver, models.Region]
        for model in targets:
            self.db.execute(delete(model))
        self.db.commit()

    # ------------------------------------------------------------ 基础档案

    def create_regions(self) -> List[models.Region]:
        regions = []
        for code, name, rtype, lng, lat, area, level in REGION_TEMPLATES:
            region = models.Region(
                code=code,
                name=name,
                region_type=rtype,
                center_lng=lng,
                center_lat=lat,
                area_km2=area,
                demand_level=level,
                status=1,
                remark=f"{rtype}功能区，需求强度 {level} 级",
            )
            self.db.add(region)
            regions.append(region)
        self.db.commit()
        for region in regions:
            self.db.refresh(region)
        self.log(f"生成区域 {len(regions)} 个")
        return regions

    def allocate_vehicles(self, regions: List[models.Region], count: int) -> np.ndarray:
        """按需求量占比分配车辆数。

        采用「按比例取整 + 小数部分从大到小补足」的确定性分配，
        并保证每个启用区域至少 2 台车，避免随机抽样产生「某区域仅 1 台车」的极端偏差。
        """
        share = self.demand_share(regions)
        weights = np.array(
            [share[r.id] * self.rng.uniform(0.80, 1.20) for r in regions], dtype=float
        )
        weights = weights / weights.sum()
        raw = weights * count
        alloc = np.maximum(np.floor(raw).astype(int), min(2, max(1, count // len(regions))))
        while int(alloc.sum()) > count:
            idx = int(np.argmax(alloc - raw))
            if alloc[idx] <= 1:
                break
            alloc[idx] -= 1
        remain = count - int(alloc.sum())
        order = np.argsort(-(raw - np.floor(raw)))
        i = 0
        while remain > 0 and len(order):
            alloc[order[i % len(order)]] += 1
            remain -= 1
            i += 1
        return alloc

    def create_vehicles(self, regions: List[models.Region], count: int) -> List[models.Vehicle]:
        """车辆按各区域需求量等比分配，并叠加 ±20% 的结构性偏差。

        偏差的作用是让部分区域长期偏紧、部分区域长期偏松，
        从而为「供需缺口分析 + 调度决策」提供真实的分析对象。
        """
        alloc = self.allocate_vehicles(regions, count)
        home_pool: List[int] = []
        for region, amount in zip(regions, alloc):
            home_pool.extend([region.id] * int(amount))
        self.rng.shuffle(home_pool)
        today = date.today()

        vehicles: List[models.Vehicle] = []
        for index in range(count):
            brand, color, energy = self.rng.choice(VEHICLE_BRANDS)
            home = home_pool[index % len(home_pool)]
            purchase = today - timedelta(days=self.rng.randint(120, 2200))
            vehicles.append(
                models.Vehicle(
                    plate_number=(
                        f"豫A·{self.rng.choice('DFGHJKLMNPQRSTUVWXY')}"
                        f"{self.rng.randint(10000, 99999)}"
                    ),
                    brand_model=brand,
                    color=color,
                    vehicle_type=self.rng.choice(VEHICLE_TYPES),
                    energy_type=energy,
                    seats=5,
                    purchase_date=purchase,
                    purchase_price=round(self.rng.uniform(7.5, 22.0), 2),
                    mileage_total=round(self.rng.uniform(20000, 260000), 2),
                    insurance_expire=today + timedelta(days=self.rng.randint(-10, 320)),
                    cert_expire=today + timedelta(days=self.rng.randint(-5, 500)),
                    next_maintenance_date=today + timedelta(days=self.rng.randint(-20, 80)),
                    maintenance_cycle_days=self.rng.choice((60, 90, 120)),
                    home_region_id=home,
                    status=1 if self.rng.random() < 0.94 else self.rng.choice((0, 2)),
                    remark=None,
                )
            )
        self.db.add_all(vehicles)
        self.db.commit()
        self.log(f"生成车辆 {len(vehicles)} 台（在营 {sum(1 for v in vehicles if v.status == 1)} 台）")
        return vehicles

    def create_drivers(self, regions: List[models.Region], count: int) -> List[models.Driver]:
        region_ids = [r.id for r in regions]
        today = date.today()

        drivers: List[models.Driver] = []
        used_cards = set()
        for index in range(count):
            name = self.rng.choice(SURNAMES) + self.rng.choice(GIVEN_NAMES)
            while True:
                id_card = (
                    f"4101{self.rng.randint(10, 99)}"
                    f"{today.year - self.rng.randint(24, 58)}"
                    f"{self.rng.randint(1, 12):02d}{self.rng.randint(1, 28):02d}"
                    f"{self.rng.randint(1000, 9999)}"
                )
                if id_card not in used_cards:
                    used_cards.add(id_card)
                    break
            hire = today - timedelta(days=self.rng.randint(30, 3000))
            drivers.append(
                models.Driver(
                    name=name,
                    gender="M" if self.rng.random() < 0.82 else "F",
                    id_card=id_card,
                    license_no=f"4101{self.rng.randint(100000000, 999999999)}",
                    qualification_no=f"CY{self.rng.randint(100000, 999999)}",
                    phone=f"1{self.rng.choice('3578')}{self.rng.randint(100000000, 999999999)}",
                    birth_date=today - timedelta(days=self.rng.randint(24, 58) * 365),
                    hire_date=hire,
                    license_expire=today + timedelta(days=self.rng.randint(-15, 900)),
                    rating=round(min(5.0, max(3.0, self.np_rng.normal(4.65, 0.28))), 2),
                    complaint_count=int(self.np_rng.poisson(0.6)),
                    violation_count=int(self.np_rng.poisson(0.9)),
                    home_region_id=self.rng.choice(region_ids),
                    status=1 if self.rng.random() < 0.95 else self.rng.choice((0, 2)),
                )
            )
        self.db.add_all(drivers)
        self.db.commit()
        self.log(f"生成驾驶员 {len(drivers)} 名（在职 {sum(1 for d in drivers if d.status == 1)} 名）")
        return drivers

    def bind_vehicle_driver(
        self, vehicles: List[models.Vehicle], drivers: List[models.Driver]
    ) -> Dict[int, List[Tuple[int, str]]]:
        """建立人车绑定与班次，返回 {车辆id: [(驾驶员id, 班次), ...]}。"""
        today = date.today()
        pool = [d for d in drivers if d.status == 1]
        self.rng.shuffle(pool)
        cursor = 0
        mapping: Dict[int, List[Tuple[int, str]]] = {}
        bindings: List[models.VehicleDriver] = []

        for vehicle in vehicles:
            if cursor >= len(pool):
                break
            assigned: List[Tuple[int, str]] = []
            first = pool[cursor]
            cursor += 1
            shift = self.rng.choice(("白班", "夜班", "全天"))
            assigned.append((first.id, shift))
            bindings.append(
                models.VehicleDriver(
                    vehicle_id=vehicle.id,
                    driver_id=first.id,
                    assign_date=today - timedelta(days=self.rng.randint(30, 900)),
                    shift=shift,
                    status=1,
                )
            )
            # 25% 的车辆配双班司机
            if cursor < len(pool) and self.rng.random() < 0.25:
                second = pool[cursor]
                cursor += 1
                second_shift = "夜班" if shift == "白班" else "白班"
                assigned.append((second.id, second_shift))
                bindings.append(
                    models.VehicleDriver(
                        vehicle_id=vehicle.id,
                        driver_id=second.id,
                        assign_date=today - timedelta(days=self.rng.randint(10, 600)),
                        shift=second_shift,
                        status=1,
                    )
                )
            mapping[vehicle.id] = assigned

        self.db.add_all(bindings)
        self.db.commit()
        self.log(f"生成人车绑定 {len(bindings)} 条（覆盖车辆 {len(mapping)} 台）")
        return mapping

    # ------------------------------------------------------------ 运营流水

    def _on_duty(
        self,
        region_id: int,
        hour: int,
        vehicles_by_region: Dict[int, List[models.Vehicle]],
        binding_map: Dict[int, List[Tuple[int, str]]],
    ) -> List[Tuple[int, int]]:
        """返回该区域该小时在岗的 (车辆id, 驾驶员id) 列表。"""
        pool = []
        for vehicle in vehicles_by_region.get(region_id, ()):  # type: ignore[arg-type]
            for driver_id, shift in binding_map.get(vehicle.id, ()):
                if shift_covers(shift, hour):
                    pool.append((vehicle.id, driver_id))
                    break
        return pool

    def generate_operations(
        self,
        regions: List[models.Region],
        vehicles: List[models.Vehicle],
        binding_map: Dict[int, List[Tuple[int, str]]],
        days: int,
        end_date: Optional[date] = None,
    ) -> None:
        """逐日逐小时生成叫车请求与营运订单。"""
        end_date = end_date or date.today()
        start_date = end_date - timedelta(days=days - 1)

        vehicles_by_region: Dict[int, List[models.Vehicle]] = {}
        for vehicle in vehicles:
            if vehicle.status != 1 or vehicle.home_region_id is None:
                continue
            vehicles_by_region.setdefault(vehicle.home_region_id, []).append(vehicle)

        # ---- 需求规模自动标定 ----
        # 运力口径必须用「在岗车辆数」而不是「在营车辆总数」：
        # 驾驶员分白班/夜班后，任一时刻只有在岗的车才能真正接单。
        on_duty_total = 0
        for hour in range(24):
            for region_id in [r.id for r in regions]:
                on_duty_total += len(
                    self._on_duty(region_id, hour, vehicles_by_region, binding_map)
                )
        avg_on_duty = on_duty_total / 24.0
        target_hourly = max(
            1.0, avg_on_duty * settings.VEHICLE_SERVICE_RATE * TARGET_LOAD
        )
        region_ids = [r.id for r in regions]
        hour_factor = {
            r.id: self.effective_hour_factor(r.region_type or "居民区") for r in regions
        }
        weekday_mean = float(WEEKDAY_FACTOR.mean())
        denominator = sum(
            r.demand_level * float(hour_factor[r.id].mean()) * weekday_mean for r in regions
        )
        base_rate = {
            r.id: target_hourly * r.demand_level / max(denominator, 1e-9) for r in regions
        }
        attraction = np.array([r.demand_level for r in regions], dtype=float)
        attraction = attraction / attraction.sum()
        coords = {r.id: (float(r.center_lng), float(r.center_lat)) for r in regions}
        self.log(
            f"需求规模标定：在营车辆 {sum(len(g) for g in vehicles_by_region.values())} 台，"
            f"平均在岗 {avg_on_duty:.1f} 台，"
            f"目标平均需求 {target_hourly:.1f} 单/小时"
        )

        req_buffer: List[dict] = []
        op_buffer: List[dict] = []
        vehicle_mileage: Dict[int, float] = {}
        seq = 0
        total_days = days

        for day_offset in range(total_days):
            day = start_date + timedelta(days=day_offset)
            weekday = day.weekday()
            holiday = is_holiday_date(day)
            weather = weighted_choice(self.rng, WEATHERS)
            weather_factor = {"晴": 1.0, "阴": 1.02, "雨": 1.22, "雪": 0.85, "雾": 0.92}[weather]
            holiday_factor = 1.18 if holiday else 1.0
            trend = 1.0 + day_offset * 0.0009

            for hour in range(24):
                peak = is_peak_hour(hour, settings.PEAK_HOURS)
                for region_id in region_ids:
                    lam = (
                        base_rate[region_id]
                        * hour_factor[region_id][hour]
                        * WEEKDAY_FACTOR[weekday]
                        * weather_factor
                        * holiday_factor
                        * trend
                    )
                    lam = max(0.02, lam)
                    demand = int(self.np_rng.poisson(lam))
                    if demand <= 0:
                        continue

                    on_duty = self._on_duty(region_id, hour, vehicles_by_region, binding_map)
                    capacity = len(on_duty) * settings.VEHICLE_SERVICE_RATE
                    if demand > 0 and capacity > 0:
                        # 满足率随「运力/需求」比下降，但下降是平缓的：
                        # 现实中乘客会延长等待，未能在本时段成行的需求并非全部流失。
                        ratio = capacity / demand
                        fulfil_p = 0.98 if ratio >= 1 else float(np.clip(ratio ** 0.6, 0.30, 0.98))
                    else:
                        fulfil_p = 0.0

                    for _ in range(demand):
                        seq += 1
                        request_dt = datetime.combine(day, dtime(hour)) + timedelta(
                            minutes=self.rng.randint(0, 59), seconds=self.rng.randint(0, 59)
                        )
                        request_no = f"REQ{day.strftime('%y%m%d')}{seq:09d}"
                        fulfilled = on_duty and self.rng.random() < fulfil_p

                        if fulfilled:
                            vehicle_id, driver_id = self.rng.choice(on_duty)
                            dropoff_id = int(self.np_rng.choice(region_ids, p=attraction))
                            if dropoff_id == region_id and self.rng.random() < 0.75:
                                dropoff_id = int(self.np_rng.choice([r for r in region_ids if r != region_id]))
                            lng1, lat1 = coords[region_id]
                            lng2, lat2 = coords[dropoff_id]
                            straight = haversine_km(lng1, lat1, lng2, lat2)
                            distance = max(
                                1.5,
                                min(42.0, straight * 1.32 * self.rng.uniform(0.8, 1.45) + 1.2),
                            )
                            speed = (23.0 if peak else 38.0) * self.rng.uniform(0.85, 1.15)
                            duration = distance / speed * 60.0
                            amount = (
                                8.0
                                + max(0.0, distance - 2.0) * 2.2
                                + max(0.0, duration - 10.0) * 0.35
                                + self.rng.uniform(-0.6, 0.9)
                            )
                            amount = round(max(8.0, amount), 1)
                            empty = round(distance * self.rng.uniform(0.18, 0.75), 2)
                            wait = int(np.clip(self.np_rng.normal(180 if peak else 110, 70), 15, 900))

                            req_buffer.append(
                                {
                                    "request_no": request_no,
                                    "region_id": region_id,
                                    "request_time": request_dt,
                                    "stat_date": day,
                                    "hour": hour,
                                    "weekday": weekday,
                                    "passenger_count": int(self.np_rng.choice([1, 1, 1, 2, 2, 3], p=[.6, .1, .05, .15, .06, .04])),
                                    "status": 2,
                                    "wait_seconds": wait,
                                    "is_peak": peak,
                                    "weather": weather,
                                    "is_holiday": holiday,
                                    "order_no": f"ORD{day.strftime('%y%m%d')}{seq:09d}",
                                    "create_time": request_dt,
                                }
                            )
                            op_buffer.append(
                                {
                                    "order_no": f"ORD{day.strftime('%y%m%d')}{seq:09d}",
                                    "vehicle_id": vehicle_id,
                                    "driver_id": driver_id,
                                    "pickup_region_id": region_id,
                                    "dropoff_region_id": dropoff_id,
                                    "start_time": request_dt + timedelta(seconds=wait),
                                    "end_time": request_dt + timedelta(seconds=wait + duration * 60),
                                    "stat_date": day,
                                    "hour": hour,
                                    "weekday": weekday,
                                    "loaded_mileage": round(distance, 2),
                                    "empty_mileage": empty,
                                    "amount": amount,
                                    "duration_minutes": round(duration, 2),
                                    "avg_speed": round(distance / max(duration / 60.0, 1e-6), 2),
                                    "passenger_count": 1,
                                    "pay_type": weighted_choice(self.rng, PAY_TYPES),
                                    "weather": weather,
                                    "is_peak": peak,
                                    "is_holiday": holiday,
                                    "create_time": request_dt,
                                }
                            )
                            vehicle_mileage[vehicle_id] = (
                                vehicle_mileage.get(vehicle_id, 0.0) + distance + empty
                            )
                        else:
                            cancelled = capacity > 0 and self.rng.random() < 0.35
                            req_buffer.append(
                                {
                                    "request_no": request_no,
                                    "region_id": region_id,
                                    "request_time": request_dt,
                                    "stat_date": day,
                                    "hour": hour,
                                    "weekday": weekday,
                                    "passenger_count": 1,
                                    "status": 3 if cancelled else 0,
                                    "wait_seconds": int(np.clip(self.np_rng.normal(320, 150), 60, 1800)),
                                    "is_peak": peak,
                                    "weather": weather,
                                    "is_holiday": holiday,
                                    "order_no": None,
                                    "create_time": request_dt,
                                }
                            )

                    if len(req_buffer) >= 6000:
                        self._flush(req_buffer, op_buffer)
                # 每日结束后落盘
            self._flush(req_buffer, op_buffer)
            self._update_mileage(vehicle_mileage)
            vehicle_mileage = {}
            if (day_offset + 1) % 10 == 0 or day_offset == total_days - 1:
                self.log(
                    f"  进度 {day_offset + 1}/{total_days} 天，"
                    f"叫车请求 {self.stats.get('requests', 0)} 条，"
                    f"营运订单 {self.stats.get('operations', 0)} 条"
                )

        self.log(
            f"运营数据生成完成：叫车请求 {self.stats.get('requests', 0)} 条，"
            f"营运订单 {self.stats.get('operations', 0)} 条"
        )

    def _flush(self, req_buffer: List[dict], op_buffer: List[dict]) -> None:
        if op_buffer:
            self.db.bulk_insert_mappings(models.OperationRecord, op_buffer)
            self.stats["operations"] = self.stats.get("operations", 0) + len(op_buffer)
            op_buffer.clear()
        if req_buffer:
            self.db.bulk_insert_mappings(models.RideRequest, req_buffer)
            self.stats["requests"] = self.stats.get("requests", 0) + len(req_buffer)
            req_buffer.clear()
        self.db.commit()

    def _update_mileage(self, vehicle_mileage: Dict[int, float]) -> None:
        """把当日行驶里程累加到车辆累计里程。"""
        if not vehicle_mileage:
            return
        for vehicle_id, mileage in vehicle_mileage.items():
            self.db.execute(
                models.Vehicle.__table__.update()
                .where(models.Vehicle.__table__.c.id == vehicle_id)
                .values(mileage_total=models.Vehicle.__table__.c.mileage_total + mileage)
            )
        self.db.commit()

    # ------------------------------------------------------------ 入口

    def run(self, days: int, vehicle_count: int, driver_count: int, reset: bool = True) -> Dict[str, int]:
        started = datetime.now()
        if reset:
            self.reset()
        regions = self.create_regions()
        vehicles = self.create_vehicles(regions, vehicle_count)
        drivers = self.create_drivers(regions, driver_count)
        mapping = self.bind_vehicle_driver(vehicles, drivers)
        self.log(f"开始生成最近 {days} 天的运营流水 ...")
        self.generate_operations(regions, vehicles, mapping, days)
        cost = (datetime.now() - started).total_seconds()
        self.log(f"全部完成，用时 {cost:.1f} 秒")
        result = {
            "regions": len(regions),
            "vehicles": len(vehicles),
            "drivers": len(drivers),
            "bindings": sum(len(v) for v in mapping.values()),
            "requests": self.stats.get("requests", 0),
            "operations": self.stats.get("operations", 0),
            "seconds": int(cost),
        }
        return result


def run_simulation(
    db: Session,
    days: int = 60,
    vehicles: int = 60,
    drivers: int = 80,
    seed: int = 20240501,
    reset: bool = True,
    verbose: bool = True,
) -> Dict[str, int]:
    simulator = DataSimulator(db, seed=seed, verbose=verbose)
    return simulator.run(days=days, vehicle_count=vehicles, driver_count=drivers, reset=reset)
