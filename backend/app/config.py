"""全局配置模块。

所有可变参数集中在此处管理，支持通过 backend/.env 文件覆盖，
避免把数据库口令、密钥、业务阈值等硬编码散落在各个模块中。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/ 目录
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _str(key: str, default: str) -> str:
    value = os.getenv(key)
    return default if value is None or value == "" else value


def _int(key: str, default: int) -> int:
    try:
        return int(_str(key, str(default)))
    except ValueError:
        return default


def _float(key: str, default: float) -> float:
    try:
        return float(_str(key, str(default)))
    except ValueError:
        return default


def _bool(key: str, default: bool) -> bool:
    return _str(key, "1" if default else "0").lower() in {"1", "true", "yes", "on"}


def _list(key: str, default):
    raw = _str(key, "")
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    """系统配置项。"""

    # ------------------------------------------------------------------ 应用
    APP_NAME = _str("APP_NAME", "城市出租车运营管理与决策支持系统")
    APP_VERSION = _str("APP_VERSION", "2.0.0")
    API_PREFIX = "/api"
    DEBUG = _bool("DEBUG", True)

    # ------------------------------------------------------------------ 安全
    SECRET_KEY = _str("SECRET_KEY", "taxi-system-dev-secret-key-change-me")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24)

    # ------------------------------------------------------------------ 数据库
    DB_HOST = _str("DB_HOST", "localhost")
    DB_PORT = _int("DB_PORT", 3306)
    DB_USER = _str("DB_USER", "root")
    DB_PASSWORD = _str("DB_PASSWORD", "123456789")
    DB_NAME = _str("DB_NAME", "taxi_db")
    SQL_ECHO = _bool("SQL_ECHO", False)

    @property
    def DATABASE_URL(self) -> str:
        """数据库连接串。

        显式配置 DATABASE_URL 时优先生效；否则按 MySQL 参数拼装。
        也支持 sqlite:///... 以便在没有 MySQL 的环境做轻量演示。
        """
        explicit = os.getenv("DATABASE_URL")
        if explicit:
            return explicit
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    CORS_ORIGINS = _list(
        "CORS_ORIGINS",
        ["http://localhost:5173", "http://127.0.0.1:5173"],
    )

    # ------------------------------------------------------- 运营业务参数
    #: 早/晚高峰时段（左闭右开），用于高峰识别与运力倾斜
    PEAK_HOURS = [(7, 9), (17, 19)]
    #: 空驶率告警阈值
    EMPTY_RATE_WARN = _float("EMPTY_RATE_WARN", 0.40)
    #: 需求未满足率告警阈值
    UNFULFILLED_RATE_WARN = _float("UNFULFILLED_RATE_WARN", 0.15)
    #: 收入环比下滑告警阈值
    INCOME_DROP_WARN = _float("INCOME_DROP_WARN", -0.20)

    # ------------------------------------------------------- 运力与调度参数
    #: 单车每小时可承接的订单数（运力折算系数）
    VEHICLE_SERVICE_RATE = _float("VEHICLE_SERVICE_RATE", 1.5)
    #: 触发调度建议的最小供需缺口（单）
    DISPATCH_MIN_GAP = _int("DISPATCH_MIN_GAP", 3)
    #: 直线距离→实际行驶距离的绕行系数
    DISPATCH_DISTANCE_FACTOR = _float("DISPATCH_DISTANCE_FACTOR", 1.35)
    #: 车辆调度成本（元/公里，含燃油与人工）
    DISPATCH_COST_PER_KM = _float("DISPATCH_COST_PER_KM", 1.80)
    #: 单车调度可接受的最小净收益（元）
    DISPATCH_MIN_NET_GAIN = _float("DISPATCH_MIN_NET_GAIN", 5.0)
    #: 单个区域单次调度最大移入车辆数
    DISPATCH_MAX_MOVE_PER_REGION = _int("DISPATCH_MAX_MOVE_PER_REGION", 8)
    #: 单个盈余区域单次最多移出车辆数
    DISPATCH_MAX_MOVE_OUT = _int("DISPATCH_MAX_MOVE_OUT", 10)

    # ------------------------------------------------------- 预测参数
    #: 默认预测时长（小时）
    FORECAST_HORIZON = _int("FORECAST_HORIZON", 24)
    #: 回测留出的验证窗口（小时，默认 7 天）
    FORECAST_VALID_HOURS = _int("FORECAST_VALID_HOURS", 24 * 7)
    #: 滚动原点回测折数
    FORECAST_FOLDS = _int("FORECAST_FOLDS", 3)
    #: 建模所需的最小历史天数
    FORECAST_MIN_HISTORY_DAYS = _int("FORECAST_MIN_HISTORY_DAYS", 14)
    #: 参与建模的最长历史天数（0 表示不限）
    FORECAST_MAX_HISTORY_DAYS = _int("FORECAST_MAX_HISTORY_DAYS", 180)
    #: 季节回看步长（小时），168 = 一周
    FORECAST_SEASONAL_LAG = _int("FORECAST_SEASONAL_LAG", 168)
    #: 模型选优使用的主指标：rmse / mae / mape
    FORECAST_SELECT_METRIC = _str("FORECAST_SELECT_METRIC", "rmse")
    #: 参与预测的模型
    FORECAST_MODELS = _list(
        "FORECAST_MODELS",
        ["mean_baseline", "seasonal_naive", "moving_average", "holt_winters",
         "linear_regression", "ensemble"],
    )

    # ------------------------------------------------------- 预警参数
    INSURANCE_WARN_DAYS = _int("INSURANCE_WARN_DAYS", 30)
    CERT_WARN_DAYS = _int("CERT_WARN_DAYS", 30)
    MAINTENANCE_WARN_DAYS = _int("MAINTENANCE_WARN_DAYS", 15)
    LICENSE_WARN_DAYS = _int("LICENSE_WARN_DAYS", 30)


settings = Settings()
