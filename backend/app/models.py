"""数据模型（ORM 实体）。

围绕「运营管理 + 数据分析 + 需求预测 + 调度决策」四层能力设计，
共 12 张表：

    基础资源：region / vehicle / driver / vehicle_driver
    运营数据：ride_request（需求侧叫车请求）/ operation_record（供给侧完成订单）
    决策支持：forecast_result（预测结果）/ dispatch_plan（调度方案）/ dispatch_order（调度指令）
    系统支撑：sys_user / sys_config / operation_log
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base

# --------------------------------------------------------------------------
# 一、基础资源
# --------------------------------------------------------------------------


class Region(Base):
    """运营区域（城市功能区网格），是需求分析与调度的空间基本单元。"""

    __tablename__ = "region"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, comment="区域编码")
    name = Column(String(50), nullable=False, comment="区域名称")
    region_type = Column(String(20), default="居民区", comment="功能区类型")
    center_lng = Column(Numeric(10, 6), comment="中心点经度")
    center_lat = Column(Numeric(10, 6), comment="中心点纬度")
    area_km2 = Column(Numeric(8, 2), default=10, comment="面积(平方公里)")
    demand_level = Column(SmallInteger, default=3, comment="需求强度等级 1-5")
    status = Column(SmallInteger, default=1, comment="1 启用 0 停用")
    remark = Column(String(200))
    create_time = Column(DateTime, default=datetime.now)

    requests = relationship("RideRequest", back_populates="region")
    pickups = relationship(
        "OperationRecord",
        back_populates="pickup_region",
        foreign_keys="OperationRecord.pickup_region_id",
    )


class Vehicle(Base):
    """营运车辆档案。"""

    __tablename__ = "vehicle"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    plate_number = Column(String(20), unique=True, nullable=False, comment="车牌号")
    brand_model = Column(String(50), nullable=False, comment="品牌型号")
    color = Column(String(20), comment="颜色")
    vehicle_type = Column(String(20), default="巡游出租车", comment="车辆类型")
    energy_type = Column(String(10), default="燃油", comment="能源类型")
    seats = Column(SmallInteger, default=5, comment="核载人数")
    purchase_date = Column(Date, comment="购置日期")
    purchase_price = Column(Numeric(10, 2), comment="购置价格(万元)")
    mileage_total = Column(Numeric(12, 2), default=0, comment="累计里程(公里)")
    insurance_expire = Column(Date, comment="保险到期日")
    cert_expire = Column(Date, comment="营运证到期日")
    next_maintenance_date = Column(Date, comment="下次保养日期")
    maintenance_cycle_days = Column(Integer, default=90, comment="保养周期(天)")
    home_region_id = Column(BigInteger, ForeignKey("region.id"), comment="常驻区域")
    status = Column(SmallInteger, default=1, comment="1 在营 0 停运 2 维修")
    remark = Column(String(200))
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    home_region = relationship("Region", foreign_keys=[home_region_id])
    operation_records = relationship("OperationRecord", back_populates="vehicle")
    assignments = relationship("VehicleDriver", back_populates="vehicle")
    dispatch_orders = relationship("DispatchOrder", back_populates="vehicle")


class Driver(Base):
    """驾驶员档案。"""

    __tablename__ = "driver"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    name = Column(String(30), nullable=False, comment="姓名")
    gender = Column(CHAR(1), default="M", comment="M 男 F 女")
    id_card = Column(String(18), unique=True, nullable=False, comment="身份证号")
    license_no = Column(String(20), nullable=False, comment="驾驶证号")
    qualification_no = Column(String(30), comment="从业资格证号")
    phone = Column(String(15), comment="联系电话")
    birth_date = Column(Date, comment="出生日期")
    hire_date = Column(Date, comment="入职日期")
    license_expire = Column(Date, comment="驾驶证有效期至")
    rating = Column(Numeric(3, 2), default=5.00, comment="服务评分 0-5")
    complaint_count = Column(Integer, default=0, comment="投诉次数")
    violation_count = Column(Integer, default=0, comment="违章次数")
    home_region_id = Column(BigInteger, ForeignKey("region.id"), comment="常驻区域")
    status = Column(SmallInteger, default=1, comment="1 在职 0 离职 2 休假")
    remark = Column(String(200))
    create_time = Column(DateTime, default=datetime.now)
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    home_region = relationship("Region", foreign_keys=[home_region_id])
    operation_records = relationship("OperationRecord", back_populates="driver")
    assignments = relationship("VehicleDriver", back_populates="driver")
    dispatch_orders = relationship("DispatchOrder", back_populates="driver")


class VehicleDriver(Base):
    """人车绑定（排班）记录。"""

    __tablename__ = "vehicle_driver"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    vehicle_id = Column(BigInteger, ForeignKey("vehicle.id"), nullable=False)
    driver_id = Column(BigInteger, ForeignKey("driver.id"), nullable=False)
    assign_date = Column(Date, comment="绑定日期")
    unassign_date = Column(Date, nullable=True, comment="解绑日期")
    shift = Column(String(10), default="白班", comment="班次：白班/夜班/全天")
    status = Column(SmallInteger, default=1, comment="1 生效 0 已解绑")
    remark = Column(String(200))
    create_time = Column(DateTime, default=datetime.now)

    vehicle = relationship("Vehicle", back_populates="assignments")
    driver = relationship("Driver", back_populates="assignments")


# --------------------------------------------------------------------------
# 二、运营数据
# --------------------------------------------------------------------------


class RideRequest(Base):
    """乘客叫车请求（需求侧原始记录）。

    与 operation_record 的区别：本表记录「需求」，包含未被满足的请求，
    是需求预测与供需缺口分析的数据来源；operation_record 记录「已完成的供给」。
    """

    __tablename__ = "ride_request"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    request_no = Column(String(32), unique=True, nullable=False, comment="请求编号")
    region_id = Column(BigInteger, ForeignKey("region.id"), nullable=False, index=True)
    request_time = Column(DateTime, nullable=False, index=True, comment="叫车时间")
    stat_date = Column(Date, nullable=False, index=True, comment="统计日期")
    hour = Column(SmallInteger, nullable=False, comment="小时 0-23")
    weekday = Column(SmallInteger, nullable=False, comment="星期 0=周一")
    passenger_count = Column(SmallInteger, default=1, comment="乘客人数")
    status = Column(SmallInteger, default=1, comment="0 无人接单 1 已接单 2 已完成 3 已取消")
    wait_seconds = Column(Integer, default=0, comment="等待时长(秒)")
    is_peak = Column(Boolean, default=False, comment="是否高峰时段")
    weather = Column(String(10), default="晴", comment="天气")
    is_holiday = Column(Boolean, default=False, comment="是否节假日")
    order_no = Column(String(32), nullable=True, comment="关联的营运订单号")
    create_time = Column(DateTime, default=datetime.now)

    region = relationship("Region", back_populates="requests")

    __table_args__ = (
        Index("ix_request_region_time", "region_id", "request_time"),
        Index("ix_request_date_hour", "stat_date", "hour"),
    )


class OperationRecord(Base):
    """营运订单（供给侧已完成行程）。"""

    __tablename__ = "operation_record"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    order_no = Column(String(32), unique=True, nullable=False, comment="订单号")
    vehicle_id = Column(BigInteger, ForeignKey("vehicle.id"), nullable=False)
    driver_id = Column(BigInteger, ForeignKey("driver.id"), nullable=False)
    pickup_region_id = Column(BigInteger, ForeignKey("region.id"), comment="上车区域")
    dropoff_region_id = Column(BigInteger, ForeignKey("region.id"), comment="下车区域")
    start_time = Column(DateTime, nullable=False, index=True, comment="上车时间")
    end_time = Column(DateTime, nullable=False, comment="下车时间")
    stat_date = Column(Date, nullable=False, index=True, comment="统计日期")
    hour = Column(SmallInteger, nullable=False, comment="上车小时")
    weekday = Column(SmallInteger, nullable=False, comment="星期 0=周一")
    loaded_mileage = Column(Numeric(10, 2), nullable=False, comment="载客里程(公里)")
    empty_mileage = Column(Numeric(10, 2), nullable=False, comment="空驶里程(公里)")
    amount = Column(Numeric(10, 2), nullable=False, comment="订单金额(元)")
    duration_minutes = Column(Numeric(8, 2), default=0, comment="行程时长(分钟)")
    avg_speed = Column(Numeric(6, 2), default=0, comment="平均速度(公里/小时)")
    passenger_count = Column(SmallInteger, default=1, comment="乘客人数")
    pay_type = Column(String(10), default="微信", comment="支付方式")
    weather = Column(String(10), default="晴")
    is_peak = Column(Boolean, default=False)
    is_holiday = Column(Boolean, default=False)
    create_time = Column(DateTime, default=datetime.now)

    vehicle = relationship("Vehicle", back_populates="operation_records")
    driver = relationship("Driver", back_populates="operation_records")
    pickup_region = relationship(
        "Region", back_populates="pickups", foreign_keys=[pickup_region_id]
    )
    dropoff_region = relationship("Region", foreign_keys=[dropoff_region_id])

    __table_args__ = (
        Index("ix_op_vehicle_date", "vehicle_id", "stat_date"),
        Index("ix_op_driver_date", "driver_id", "stat_date"),
        Index("ix_op_region_date", "pickup_region_id", "stat_date"),
        Index("ix_op_date_hour", "stat_date", "hour"),
    )


# --------------------------------------------------------------------------
# 三、决策支持
# --------------------------------------------------------------------------


class ForecastResult(Base):
    """需求预测结果（缓存每次预测，便于回溯与准确率评估）。"""

    __tablename__ = "forecast_result"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    batch_no = Column(String(32), nullable=False, index=True, comment="预测批次号")
    region_id = Column(BigInteger, ForeignKey("region.id"), nullable=True, comment="区域，NULL 表示全域")
    target_time = Column(DateTime, nullable=False, index=True, comment="预测目标时刻")
    target_date = Column(Date, nullable=False, index=True)
    hour = Column(SmallInteger, nullable=False)
    model_name = Column(String(30), nullable=False, comment="所用模型")
    predicted_value = Column(Numeric(10, 2), nullable=False, comment="预测需求量(单)")
    lower_bound = Column(Numeric(10, 2), comment="置信下界")
    upper_bound = Column(Numeric(10, 2), comment="置信上界")
    actual_value = Column(Numeric(10, 2), nullable=True, comment="事后回填的真实值")
    mape = Column(Numeric(6, 2), comment="该模型回测 MAPE(%)")
    horizon = Column(Integer, default=24, comment="预测步长(小时)")
    created_by = Column(String(30))
    create_time = Column(DateTime, default=datetime.now)

    region = relationship("Region", foreign_keys=[region_id])


class DispatchPlan(Base):
    """调度方案（一次生成的整批调度建议）。"""

    __tablename__ = "dispatch_plan"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    plan_no = Column(String(32), unique=True, nullable=False, comment="方案编号")
    plan_date = Column(Date, nullable=False, index=True, comment="调度日期")
    target_hour = Column(SmallInteger, nullable=False, comment="目标时段(小时)")
    strategy = Column(String(30), default="greedy", comment="greedy 贪心 / hungarian 匈牙利最优")
    forecast_model = Column(String(30), comment="需求预测所用模型")
    total_demand = Column(Numeric(12, 2), default=0, comment="预测总需求")
    total_supply = Column(Numeric(12, 2), default=0, comment="可用运力")
    total_gap = Column(Numeric(12, 2), default=0, comment="总供需缺口")
    dispatch_count = Column(Integer, default=0, comment="调度车辆数")
    expected_gain = Column(Numeric(12, 2), default=0, comment="预期净收益(元)")
    status = Column(SmallInteger, default=0, comment="0 草稿 1 已下发 2 执行中 3 已完成 4 已取消")
    remark = Column(String(255))
    created_by = Column(String(30))
    create_time = Column(DateTime, default=datetime.now)

    orders = relationship(
        "DispatchOrder", back_populates="plan", cascade="all, delete-orphan"
    )


class DispatchOrder(Base):
    """调度指令（针对单车的具体调度动作）。"""

    __tablename__ = "dispatch_order"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    plan_id = Column(BigInteger, ForeignKey("dispatch_plan.id"), nullable=False, index=True)
    dispatch_no = Column(String(32), unique=True, nullable=False, comment="调度单号")
    vehicle_id = Column(BigInteger, ForeignKey("vehicle.id"), nullable=False)
    driver_id = Column(BigInteger, ForeignKey("driver.id"), nullable=True)
    from_region_id = Column(BigInteger, ForeignKey("region.id"), nullable=False, comment="调出区域")
    to_region_id = Column(BigInteger, ForeignKey("region.id"), nullable=False, comment="调入区域")
    start_hour = Column(SmallInteger, nullable=False, comment="建议出发时段")
    end_hour = Column(SmallInteger, nullable=False, comment="目标服务时段")
    predicted_demand = Column(Numeric(10, 2), comment="目标区域预测需求")
    predicted_supply = Column(Numeric(10, 2), comment="目标区域可用运力")
    gap = Column(Numeric(10, 2), comment="缺口(单)")
    distance_km = Column(Numeric(8, 2), comment="调度距离(公里)")
    expected_revenue = Column(Numeric(10, 2), comment="预期增收(元)")
    expected_cost = Column(Numeric(10, 2), comment="预期成本(元)")
    expected_gain = Column(Numeric(10, 2), comment="预期净收益(元)")
    priority = Column(SmallInteger, default=3, comment="优先级 1 高 2 中 3 低")
    status = Column(SmallInteger, default=0, comment="0 待执行 1 执行中 2 已完成 3 已拒绝 4 已取消")
    executed_time = Column(DateTime, nullable=True, comment="执行时间")
    feedback = Column(String(255), comment="执行反馈")
    remark = Column(String(255))
    create_time = Column(DateTime, default=datetime.now)

    plan = relationship("DispatchPlan", back_populates="orders")
    vehicle = relationship("Vehicle", back_populates="dispatch_orders")
    driver = relationship("Driver", back_populates="dispatch_orders")
    from_region = relationship("Region", foreign_keys=[from_region_id])
    to_region = relationship("Region", foreign_keys=[to_region_id])

    __table_args__ = (
        Index("ix_dispatch_plan_status", "plan_id", "status"),
        Index("ix_dispatch_target", "to_region_id", "start_hour"),
    )


# --------------------------------------------------------------------------
# 四、系统支撑
# --------------------------------------------------------------------------


class User(Base):
    """系统用户。"""

    __tablename__ = "sys_user"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    username = Column(String(30), unique=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    real_name = Column(String(30))
    role = Column(String(20), default="operator", comment="admin 管理员 / operator 调度员 / viewer 只读")
    phone = Column(String(15))
    status = Column(SmallInteger, default=1, comment="1 启用 0 禁用")
    last_login = Column(DateTime)
    create_time = Column(DateTime, default=datetime.now)


class SysConfig(Base):
    """业务参数配置（预警阈值、调度参数等可在界面上调整）。"""

    __tablename__ = "sys_config"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    config_key = Column(String(50), unique=True, nullable=False)
    config_value = Column(String(200), nullable=False)
    config_name = Column(String(50))
    config_group = Column(String(30), default="业务参数")
    value_type = Column(String(10), default="float", comment="int/float/str/bool")
    description = Column(String(255))
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class OperationLog(Base):
    """操作日志。"""

    __tablename__ = "operation_log"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger)
    username = Column(String(30))
    module = Column(String(30))
    operation = Column(String(100), comment="操作描述")
    method = Column(String(10), comment="HTTP 方法")
    path = Column(String(200))
    ip = Column(String(50))
    status_code = Column(Integer)
    cost_ms = Column(Integer, comment="耗时(毫秒)")
    create_time = Column(DateTime, default=datetime.now, index=True)
