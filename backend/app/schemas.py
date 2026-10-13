"""Pydantic 数据校验模型（请求体 / 响应体）。"""
from datetime import date, datetime
from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    """统一分页响应结构。"""

    total: int = 0
    page: int = 1
    page_size: int = 20
    items: List[T] = Field(default_factory=list)


class Message(BaseModel):
    message: str


# --------------------------------------------------------------------------
# 认证 / 用户
# --------------------------------------------------------------------------


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0


class UserLogin(BaseModel):
    username: str = Field(min_length=2, max_length=30)
    password: str = Field(min_length=4, max_length=64)


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=30)
    password: str = Field(min_length=4, max_length=64)
    real_name: str = "未命名"
    role: str = "operator"
    phone: Optional[str] = None


class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[int] = None


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=4, max_length=64)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=4, max_length=64)


class UserOut(ORMBase):
    id: int
    username: str
    real_name: Optional[str] = None
    role: str
    phone: Optional[str] = None
    status: int
    last_login: Optional[datetime] = None
    create_time: Optional[datetime] = None


# --------------------------------------------------------------------------
# 区域
# --------------------------------------------------------------------------


class RegionBase(BaseModel):
    code: str = Field(max_length=20)
    name: str = Field(max_length=50)
    region_type: str = "居民区"
    center_lng: Optional[float] = None
    center_lat: Optional[float] = None
    area_km2: Optional[float] = 10
    demand_level: int = 3
    status: int = 1
    remark: Optional[str] = None


class RegionOut(ORMBase):
    id: int
    code: str
    name: str
    region_type: Optional[str] = None
    center_lng: Optional[float] = None
    center_lat: Optional[float] = None
    area_km2: Optional[float] = None
    demand_level: Optional[int] = None
    status: int
    remark: Optional[str] = None
    create_time: Optional[datetime] = None


# --------------------------------------------------------------------------
# 车辆
# --------------------------------------------------------------------------


class VehicleBase(BaseModel):
    plate_number: str = Field(max_length=20)
    brand_model: str = Field(max_length=50)
    color: Optional[str] = None
    vehicle_type: str = "巡游出租车"
    energy_type: str = "燃油"
    seats: int = 5
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    mileage_total: Optional[float] = 0
    insurance_expire: Optional[date] = None
    cert_expire: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    maintenance_cycle_days: int = 90
    home_region_id: Optional[int] = None
    status: int = 1
    remark: Optional[str] = None


class VehicleOut(ORMBase):
    id: int
    plate_number: str
    brand_model: str
    color: Optional[str] = None
    vehicle_type: Optional[str] = None
    energy_type: Optional[str] = None
    seats: Optional[int] = None
    purchase_date: Optional[date] = None
    purchase_price: Optional[float] = None
    mileage_total: Optional[float] = None
    insurance_expire: Optional[date] = None
    cert_expire: Optional[date] = None
    next_maintenance_date: Optional[date] = None
    maintenance_cycle_days: Optional[int] = None
    home_region_id: Optional[int] = None
    home_region_name: Optional[str] = None
    status: int
    remark: Optional[str] = None
    create_time: Optional[datetime] = None
    # 由运营数据聚合出的扩展信息
    bound_driver_id: Optional[int] = None
    bound_driver_name: Optional[str] = None
    order_count: Optional[int] = None
    total_income: Optional[float] = None


# --------------------------------------------------------------------------
# 驾驶员
# --------------------------------------------------------------------------


class DriverBase(BaseModel):
    name: str = Field(max_length=30)
    gender: str = "M"
    id_card: str = Field(max_length=18)
    license_no: str = Field(max_length=20)
    qualification_no: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    hire_date: Optional[date] = None
    license_expire: Optional[date] = None
    rating: Optional[float] = 5.0
    complaint_count: int = 0
    violation_count: int = 0
    home_region_id: Optional[int] = None
    status: int = 1
    remark: Optional[str] = None


class DriverOut(ORMBase):
    id: int
    name: str
    gender: Optional[str] = None
    id_card: str
    license_no: str
    qualification_no: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    hire_date: Optional[date] = None
    license_expire: Optional[date] = None
    rating: Optional[float] = None
    complaint_count: Optional[int] = None
    violation_count: Optional[int] = None
    home_region_id: Optional[int] = None
    home_region_name: Optional[str] = None
    status: int
    remark: Optional[str] = None
    create_time: Optional[datetime] = None
    bound_vehicle_id: Optional[int] = None
    bound_plate: Optional[str] = None
    order_count: Optional[int] = None
    total_income: Optional[float] = None


# --------------------------------------------------------------------------
# 人车绑定
# --------------------------------------------------------------------------


class AssignmentCreate(BaseModel):
    vehicle_id: int
    driver_id: int
    assign_date: Optional[date] = None
    shift: str = "白班"
    remark: Optional[str] = None


class AssignmentOut(ORMBase):
    id: int
    vehicle_id: int
    driver_id: int
    assign_date: Optional[date] = None
    unassign_date: Optional[date] = None
    shift: Optional[str] = None
    status: int
    remark: Optional[str] = None
    plate_number: Optional[str] = None
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None


# --------------------------------------------------------------------------
# 叫车请求（需求）
# --------------------------------------------------------------------------


class RideRequestCreate(BaseModel):
    request_no: Optional[str] = None
    region_id: int
    request_time: datetime
    passenger_count: int = 1
    status: int = 1
    wait_seconds: int = 0
    weather: str = "晴"
    order_no: Optional[str] = None


class RideRequestOut(ORMBase):
    id: int
    request_no: str
    region_id: int
    region_name: Optional[str] = None
    request_time: datetime
    stat_date: date
    hour: int
    weekday: int
    passenger_count: Optional[int] = None
    status: int
    wait_seconds: Optional[int] = None
    is_peak: Optional[bool] = None
    weather: Optional[str] = None
    is_holiday: Optional[bool] = None
    order_no: Optional[str] = None


# --------------------------------------------------------------------------
# 营运订单
# --------------------------------------------------------------------------


class OperationRecordCreate(BaseModel):
    order_no: Optional[str] = None
    vehicle_id: int
    driver_id: int
    pickup_region_id: Optional[int] = None
    dropoff_region_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    loaded_mileage: float
    empty_mileage: float = 0
    amount: float
    passenger_count: int = 1
    pay_type: Optional[str] = "微信"
    weather: Optional[str] = "晴"


class OperationRecordUpdate(BaseModel):
    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None
    pickup_region_id: Optional[int] = None
    dropoff_region_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    loaded_mileage: Optional[float] = None
    empty_mileage: Optional[float] = None
    amount: Optional[float] = None
    passenger_count: Optional[int] = None
    pay_type: Optional[str] = None
    weather: Optional[str] = None


class OperationRecordOut(ORMBase):
    id: int
    order_no: str
    vehicle_id: int
    driver_id: int
    pickup_region_id: Optional[int] = None
    dropoff_region_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    stat_date: Optional[date] = None
    hour: Optional[int] = None
    weekday: Optional[int] = None
    loaded_mileage: float
    empty_mileage: float
    amount: float
    duration_minutes: Optional[float] = None
    avg_speed: Optional[float] = None
    passenger_count: Optional[int] = None
    pay_type: Optional[str] = None
    weather: Optional[str] = None
    is_peak: Optional[bool] = None
    # 关联展示字段
    plate_number: Optional[str] = None
    driver_name: Optional[str] = None
    pickup_region_name: Optional[str] = None
    dropoff_region_name: Optional[str] = None


class ImportResult(BaseModel):
    success: bool = True
    total_rows: int = 0
    imported: int = 0
    duplicated: int = 0
    error_rows: List[int] = Field(default_factory=list)
    error_messages: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# 系统配置 / 日志
# --------------------------------------------------------------------------


class SysConfigUpdate(BaseModel):
    config_value: str


class SysConfigOut(ORMBase):
    id: int
    config_key: str
    config_value: str
    config_name: Optional[str] = None
    config_group: Optional[str] = None
    value_type: Optional[str] = None
    description: Optional[str] = None
    update_time: Optional[datetime] = None


class OperationLogOut(ORMBase):
    id: int
    username: Optional[str] = None
    module: Optional[str] = None
    operation: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    ip: Optional[str] = None
    status_code: Optional[int] = None
    cost_ms: Optional[int] = None
    create_time: Optional[datetime] = None


# --------------------------------------------------------------------------
# 需求预测
# --------------------------------------------------------------------------


class ForecastRequest(BaseModel):
    region_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    horizon: int = 24
    models: Optional[List[str]] = None
    auto_select: bool = True


class ForecastPoint(BaseModel):
    time: datetime
    value: float
    lower: float = 0
    upper: float = 0
    actual: Optional[float] = None


class ModelMetric(BaseModel):
    model: str
    model_label: str
    mae: float
    rmse: float
    mape: Optional[float] = None
    r2: Optional[float] = None
    is_best: bool = False


class ForecastResponse(BaseModel):
    region_id: Optional[int] = None
    region_name: str = "全域"
    model: str
    model_label: str
    horizon: int
    history_days: int
    generated_at: datetime
    batch_no: str
    #: 模型选优所使用的主指标（rmse / mae / mape）
    select_metric: Optional[str] = None
    #: 滚动原点回测折数
    folds: Optional[int] = None
    #: 每折回测的预测步长（小时）
    valid_hours: Optional[int] = None
    metrics: List[ModelMetric] = Field(default_factory=list)
    points: List[ForecastPoint] = Field(default_factory=list)
    #: 历史同期曲线，供前端对照展示
    history: List[ForecastPoint] = Field(default_factory=list)


class ForecastAccuracyOut(BaseModel):
    model_label: str
    sample_count: int
    mae: float
    rmse: float
    mape: Optional[float] = None
    accuracy: Optional[float] = None


# --------------------------------------------------------------------------
# 调度决策
# --------------------------------------------------------------------------


class DispatchGenerateRequest(BaseModel):
    plan_date: Optional[date] = None
    target_hour: Optional[int] = Field(default=None, ge=0, le=23)
    strategy: str = "hungarian"
    forecast_model: Optional[str] = None
    auto_save: bool = True


class RegionSupplyDemand(BaseModel):
    region_id: int
    region_name: str
    region_type: Optional[str] = None
    predicted_demand: float
    current_supply: float
    effective_supply: float
    gap: float
    gap_level: str
    expected_revenue: float = 0


class DispatchOrderOut(ORMBase):
    id: Optional[int] = None
    plan_id: Optional[int] = None
    dispatch_no: Optional[str] = None
    vehicle_id: int
    driver_id: Optional[int] = None
    from_region_id: int
    to_region_id: int
    start_hour: int
    end_hour: int
    predicted_demand: Optional[float] = None
    predicted_supply: Optional[float] = None
    gap: Optional[float] = None
    distance_km: Optional[float] = None
    expected_revenue: Optional[float] = None
    expected_cost: Optional[float] = None
    expected_gain: Optional[float] = None
    priority: Optional[int] = None
    status: int
    executed_time: Optional[datetime] = None
    feedback: Optional[str] = None
    remark: Optional[str] = None
    create_time: Optional[datetime] = None
    plate_number: Optional[str] = None
    driver_name: Optional[str] = None
    from_region_name: Optional[str] = None
    to_region_name: Optional[str] = None


class DispatchPlanOut(ORMBase):
    id: Optional[int] = None
    plan_no: str
    plan_date: date
    target_hour: int
    strategy: Optional[str] = None
    forecast_model: Optional[str] = None
    total_demand: Optional[float] = None
    total_supply: Optional[float] = None
    total_gap: Optional[float] = None
    dispatch_count: Optional[int] = None
    expected_gain: Optional[float] = None
    status: int
    remark: Optional[str] = None
    created_by: Optional[str] = None
    create_time: Optional[datetime] = None
    done_count: Optional[int] = None
    orders: Optional[List[DispatchOrderOut]] = None


class DispatchGenerateResponse(BaseModel):
    plan: Optional[DispatchPlanOut] = None
    region_status: List[RegionSupplyDemand] = Field(default_factory=list)
    strategy_compare: List[dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class DispatchFeedback(BaseModel):
    status: int = Field(description="2 已完成 3 已拒绝 4 已取消")
    feedback: Optional[str] = None


class DispatchEffectOut(BaseModel):
    plan_id: int
    plan_no: str
    dispatch_count: int
    done_count: int
    done_ratio: float
    expected_gain: float
    actual_gain: float
    accuracy: Optional[float] = None
    detail: List[dict[str, Any]] = Field(default_factory=list)
