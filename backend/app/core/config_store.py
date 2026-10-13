"""业务参数配置存储。

系统参数以键值对形式存放在 ``sys_config`` 表中，应用启动时载入并覆盖
``settings`` 单例上的同名属性，从而让界面上修改阈值后立即对所有业务模块生效。
"""
from typing import Any, Dict, List, Tuple

from sqlalchemy.orm import Session

from .. import models
from ..config import settings

#: (配置键, 默认值, 名称, 分组, 类型, 说明)
CONFIG_DEFAULTS: Tuple[Tuple[str, Any, str, str, str, str], ...] = (
    ("EMPTY_RATE_WARN", 0.40, "空驶率预警阈值", "运营分析", "float",
     "近 7 天空驶里程占比超过该比例时产生预警（0.4 = 40%）"),
    ("UNFULFILLED_RATE_WARN", 0.15, "需求未满足率预警阈值", "运营分析", "float",
     "区域叫车未满足率超过该比例时产生预警"),
    ("INCOME_DROP_WARN", -0.20, "收入下滑预警阈值", "运营分析", "float",
     "收入环比降幅超过该比例时产生预警（-0.2 = 下降 20%）"),
    ("VEHICLE_SERVICE_RATE", 1.50, "单车小时服务能力", "调度决策", "float",
     "一辆车一小时平均可承接的订单数，用于把车辆数折算为可服务订单数"),
    ("DISPATCH_MIN_GAP", 3, "触发调度的最小缺口", "调度决策", "int",
     "区域供需缺口小于该值时不下发调度建议"),
    ("DISPATCH_DISTANCE_FACTOR", 1.35, "距离绕行系数", "调度决策", "float",
     "直线距离折算为实际行驶距离的系数"),
    ("DISPATCH_COST_PER_KM", 1.80, "调度单位里程成本(元)", "调度决策", "float",
     "车辆空驶调度的燃油与人工成本"),
    ("DISPATCH_MIN_NET_GAIN", 5.0, "最小可接受净收益(元)", "调度决策", "float",
     "净收益低于该值的调度组合不予采纳"),
    ("DISPATCH_MAX_MOVE_PER_REGION", 8, "单区域最大调入车辆数", "调度决策", "int",
     "避免一次性向同一区域过度投放运力"),
    ("DISPATCH_MAX_MOVE_OUT", 10, "单区域最大调出车辆数", "调度决策", "int",
     "避免把盈余区域的运力抽空"),
    ("FORECAST_HORIZON", 24, "默认预测时长(小时)", "需求预测", "int",
     "需求预测默认预测未来多少小时"),
    ("FORECAST_VALID_HOURS", 168, "回测验证窗口(小时)", "需求预测", "int",
     "滚动回测每一折预测的小时数，168 表示 7 天"),
    ("FORECAST_FOLDS", 3, "滚动回测折数", "需求预测", "int",
     "折数越多评估越稳健，计算耗时也越长"),
    ("FORECAST_MIN_HISTORY_DAYS", 14, "建模最少历史天数", "需求预测", "int",
     "历史数据少于该天数时拒绝建模"),
    ("FORECAST_SELECT_METRIC", "rmse", "模型选优主指标", "需求预测", "str",
     "可选 rmse / mae / mape"),
    ("INSURANCE_WARN_DAYS", 30, "保险到期提醒(天)", "预警提醒", "int", "提前多少天提醒车辆保险到期"),
    ("CERT_WARN_DAYS", 30, "营运证到期提醒(天)", "预警提醒", "int", "提前多少天提醒营运证到期"),
    ("MAINTENANCE_WARN_DAYS", 15, "保养到期提醒(天)", "预警提醒", "int", "提前多少天提醒车辆保养"),
    ("LICENSE_WARN_DAYS", 30, "驾驶证到期提醒(天)", "预警提醒", "int", "提前多少天提醒驾驶证到期"),
)


def _cast(value: str, value_type: str) -> Any:
    if value_type == "int":
        return int(float(value))
    if value_type == "float":
        return float(value)
    if value_type == "bool":
        return str(value).lower() in ("1", "true", "yes", "on")
    return value


def ensure_defaults(db: Session) -> int:
    """补齐缺失的配置项。"""
    existing = {row.config_key for row in db.query(models.SysConfig).all()}
    created = 0
    for key, value, name, group, value_type, description in CONFIG_DEFAULTS:
        if key in existing:
            continue
        db.add(
            models.SysConfig(
                config_key=key,
                config_value=str(value),
                config_name=name,
                config_group=group,
                value_type=value_type,
                description=description,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def load_overrides(db: Session) -> Dict[str, Any]:
    """把数据库中的配置覆盖到 settings 单例上，返回生效的配置字典。"""
    applied: Dict[str, Any] = {}
    for row in db.query(models.SysConfig).all():
        if not hasattr(settings, row.config_key):
            continue
        try:
            value = _cast(row.config_value, row.value_type or "str")
        except (TypeError, ValueError):
            continue
        setattr(settings, row.config_key, value)
        applied[row.config_key] = value
    return applied


def list_configs(db: Session) -> List[models.SysConfig]:
    return (
        db.query(models.SysConfig)
        .order_by(models.SysConfig.config_group, models.SysConfig.id)
        .all()
    )
