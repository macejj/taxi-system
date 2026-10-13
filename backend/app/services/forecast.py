"""需求预测引擎。

设计思路
--------
1. **数据准备**：把 ``ride_request`` 按「区域 × 小时」聚合成等间隔小时序列，
   缺失小时补 0（该小时确实无人叫车），保证序列连续。
2. **特征构造**：小时(23 个哑变量)、星期(6 个哑变量)、高峰标记、节假日标记、雨天标记。
3. **模型库**（全部基于 numpy 手工实现，无 scikit-learn 等重依赖）：

   ==================  ============================================================
   模型                说明
   ==================  ============================================================
   mean_baseline       均值基线（仅作参照，不参与选优）
   seasonal_naive      季节朴素法：直接取上周同一时刻的需求
   moving_average      季节移动平均：同小时最近 k 周需求的算术平均
   holt_winters        三次指数平滑（水平/趋势/季节），平滑系数与季节模式网格寻优
   linear_regression   多元线性回归（最小二乘，含趋势项与哑变量）
   ensemble            组合模型：以回测 RMSE 的倒数为权重加权平均
   ==================  ============================================================

4. **滚动原点回测**：以历史末端为预测原点，向前滚动若干折，每折从原点
   *直接* 预测未来 N 小时（多步直接预测），从而保证任何模型都不会使用
   预测窗口内的真实值——这是评价预测模型的正确方式。
   汇总各折误差得到 MAE / RMSE / MAPE / R²，并按主指标自动选优。
5. **输出**：最优模型在全部历史数据上重新训练后预测未来 ``horizon`` 小时，
   并基于回测残差标准差给出近似 95% 置信区间。
"""
from __future__ import annotations

import math
import warnings
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..core.sqlutil import date_range as _date_range
from ..core.sqlutil import datetime_bounds, is_peak_hour

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

MODEL_LABELS: Dict[str, str] = {
    "mean_baseline": "均值基线(参照)",
    "seasonal_naive": "季节朴素法",
    "moving_average": "季节移动平均",
    "holt_winters": "Holt-Winters 三次指数平滑",
    "linear_regression": "多元线性回归",
    "ensemble": "组合模型(逆误差加权)",
}

#: 参选模型（不含仅作参照的基线）
SELECTABLE_MODELS = (
    "seasonal_naive",
    "moving_average",
    "holt_winters",
    "linear_regression",
    "ensemble",
)

RAINY_WEATHER = ("雨", "雪", "暴雨", "大雨")

#: Holt-Winters 平滑系数网格（粗网格，兼顾效果与速度）
_HW_GRID = {
    "alpha": (0.2, 0.5, 0.8),
    "beta": (0.05, 0.15),
    "gamma": (0.1, 0.4),
    #: 趋势阻尼系数，<1 可抑制多步预测时趋势被线性外推放大
    "phi": (0.9, 1.0),
}

#: 一周的小时数，作为季节周期
WEEK_HOURS = 168


# --------------------------------------------------------------------------
# 一、纯算法层（不依赖数据库，可独立单元测试）
# --------------------------------------------------------------------------


def build_features(
    index: pd.DatetimeIndex,
    holidays: Optional[set] = None,
    rain_hours: Optional[set] = None,
) -> pd.DataFrame:
    """根据时间索引构造回归特征矩阵。

    holidays / rain_hours 未知时（例如未来时刻）留空即可，
    此时对应特征取 0，即假设「未来不是节假日、不下雨」。
    """
    hour = index.hour.to_numpy()
    weekday = index.dayofweek.to_numpy()
    holiday_flag = np.zeros(len(index))
    rain_flag = np.zeros(len(index))
    if holidays:
        holiday_flag = np.array([1.0 if ts.date() in holidays else 0.0 for ts in index])
    if rain_hours:
        rain_flag = np.array(
            [
                1.0
                if ts.to_pydatetime().replace(minute=0, second=0, microsecond=0) in rain_hours
                else 0.0
                for ts in index
            ]
        )
    return pd.DataFrame(
        {
            "hour": hour,
            "weekday": weekday,
            "is_peak": np.array(
                [1.0 if is_peak_hour(int(h), settings.PEAK_HOURS) else 0.0 for h in hour]
            ),
            "is_holiday": holiday_flag,
            "rain": rain_flag,
        },
        index=index,
    )


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Optional[float]]:
    """计算 MAE / RMSE / MAPE / R²。"""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) == 0:
        return {"mae": 0.0, "rmse": 0.0, "mape": None, "r2": None}
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    # MAPE：分母做 max(actual, 1) 平滑，避免夜间 0 需求导致除零
    denom = np.maximum(np.abs(y_true), 1.0)
    mape = float(np.mean(np.abs(err) / denom) * 100)
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = None if ss_tot <= 0 else float(1 - ss_res / ss_tot)
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 4), "r2": r2}


def _fill_missing(values: np.ndarray, train: pd.Series) -> np.ndarray:
    """把回看取到的缺失值用「同小时历史均值」或整体均值补齐。"""
    values = np.asarray(values, dtype=float)
    if not np.isnan(values).any():
        return values
    fallback = float(train.mean()) if len(train) else 0.0
    return np.where(np.isnan(values), fallback, values)


# ---------------------------------------------------------------- 基线模型


def mean_baseline_forecast(train: pd.Series, horizon: int) -> np.ndarray:
    """均值基线：用训练期平均值作为常数预测。"""
    value = float(train.mean()) if len(train) else 0.0
    return np.full(horizon, max(value, 0.0))


# ---------------------------------------------------------------- 季节朴素法


def seasonal_naive_forecast(
    train: pd.Series, target: pd.DatetimeIndex, lag_hours: int = WEEK_HOURS
) -> np.ndarray:
    """季节朴素法：ŷ(t) = y(t - lag)，默认取上周同一时刻。

    ``lag_hours`` 必须不小于预测步长，否则会用到预测窗口内的真实值。
    """
    out = train.reindex(target - pd.Timedelta(hours=lag_hours)).to_numpy(dtype=float)
    out = _fill_missing(out, train)
    return np.clip(np.nan_to_num(out), 0, None)


# ------------------------------------------------------------ 季节移动平均


def moving_average_forecast(
    train: pd.Series,
    target: pd.DatetimeIndex,
    period: int = WEEK_HOURS,
    weeks: int = 3,
) -> np.ndarray:
    """季节移动平均：对同小时最近 ``weeks`` 个（以 ``period`` 为步长的）观测取平均。

    全部回看步长均为 ``period`` 的整数倍且 ≥ ``period``，
    因此当 ``period >= horizon`` 时不会触及预测窗口内的数据。
    """
    rows = []
    for w in range(1, weeks + 1):
        lag = period * w
        rows.append(train.reindex(target - pd.Timedelta(hours=lag)).to_numpy(dtype=float))
    if not rows:
        return mean_baseline_forecast(train, len(target))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        stacked = np.vstack(rows)
        counts = np.sum(~np.isnan(stacked), axis=0)
        out = np.where(counts > 0, np.nan_to_num(stacked).sum(axis=0) / np.maximum(counts, 1), np.nan)
    out = _fill_missing(out, train)
    return np.clip(np.nan_to_num(out), 0, None)


# --------------------------------------------------------- Holt-Winters


def _hw_run(
    y: np.ndarray,
    period: int,
    alpha: float,
    beta: float,
    gamma: float,
    seasonal: str,
    phi: float = 1.0,
) -> Tuple[np.ndarray, float, float, np.ndarray]:
    """执行一次带阻尼趋势的 Holt-Winters 递推。

    :param phi: 趋势阻尼系数（1.0 表示不阻尼）。引入 φ 可显著改善多步预测，
        避免线性趋势在长预测期上被过度外推。
    :return: (拟合值, 末期水平, 末期趋势, 季节因子数组)
    """
    n = len(y)
    seasonals = np.zeros(n + period * 2 + 1)
    level = float(np.mean(y[:period]))
    if seasonal == "add":
        seasonals[:period] = y[:period] - level
    else:
        seasonals[:period] = np.where(y[:period] > 1e-9, y[:period] / max(level, 1e-9), 1.0)
    trend = (float(np.mean(y[period:2 * period])) - float(np.mean(y[:period]))) / period

    fitted = np.zeros(n)
    for i in range(n):
        s = seasonals[i]
        base = level + phi * trend
        fitted[i] = base + s if seasonal == "add" else base * s
        actual = float(y[i])
        prev_level = level
        if seasonal == "add":
            level = alpha * (actual - s) + (1 - alpha) * base
        else:
            ratio = actual / s if abs(s) > 1e-6 else actual
            level = alpha * ratio + (1 - alpha) * base
        trend = beta * (level - prev_level) + (1 - beta) * phi * trend
        if seasonal == "add":
            seasonals[i + period] = gamma * (actual - level) + (1 - gamma) * s
        else:
            ratio = actual / level if abs(level) > 1e-6 else 1.0
            seasonals[i + period] = gamma * ratio + (1 - gamma) * s
    return fitted, level, trend, seasonals


def _damped_trend_sum(phi: float, h: int) -> float:
    """Σ_{i=1..h} φ^i，用于阻尼趋势的 h 步预测。"""
    if abs(phi - 1.0) < 1e-9:
        return float(h)
    return float(phi * (1 - phi ** h) / (1 - phi))


def optimize_hw(
    y: np.ndarray, period: int, allow_multiplicative: bool
) -> Tuple[Dict[str, float], str]:
    """在平滑系数网格上寻优，同时选择加法/乘法季节模式（以样本内 SSE 最小为准）。"""
    modes = ["add", "mul"] if allow_multiplicative else ["add"]
    best_sse = math.inf
    best: Tuple[Dict[str, float], str] = (
        {"alpha": 0.3, "beta": 0.1, "gamma": 0.3, "phi": 0.95},
        "add",
    )
    for mode in modes:
        for a in _HW_GRID["alpha"]:
            for b in _HW_GRID["beta"]:
                for g in _HW_GRID["gamma"]:
                    for p in _HW_GRID["phi"]:
                        try:
                            fitted, _, _, _ = _hw_run(y, period, a, b, g, mode, p)
                        except Exception:
                            continue
                        sse = float(np.sum((y - fitted) ** 2))
                        if sse < best_sse:
                            best_sse = sse
                            best = ({"alpha": a, "beta": b, "gamma": g, "phi": p}, mode)
    return best


def holt_winters_forecast(
    train: pd.Series,
    horizon: int,
    period: int = WEEK_HOURS,
    seasonal: Optional[str] = None,
    params: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """带阻尼趋势的三次指数平滑预测。

    :param period: 季节周期，24 表示日周期，168 表示周周期
    :param seasonal: ``add`` 加法模型 / ``mul`` 乘法模型，None 时自动寻优
    :param params: 平滑系数，None 时在网格上寻优（最小化样本内 SSE）
    """
    y = train.to_numpy(dtype=float)
    n = len(y)
    if n < 2 * period:
        period = 24
    if n < 2 * period:
        return mean_baseline_forecast(train, horizon)

    # 乘法模型要求序列严格远离 0（出租车需求夜间可能为 0，此时只能用加法模型）
    allow_mul = bool(y.min() >= 2.0)

    if params is None or seasonal is None:
        best_params, best_mode = optimize_hw(y, period, allow_mul)
        params = params or best_params
        seasonal = seasonal or best_mode
    if seasonal == "mul" and not allow_mul:
        seasonal = "add"

    phi = float(params.get("phi", 1.0))
    _, level, trend, seasonals = _hw_run(
        y, period, params["alpha"], params["beta"], params["gamma"], seasonal, phi
    )

    out = np.empty(horizon)
    for h in range(1, horizon + 1):
        s = seasonals[n + ((h - 1) % period)]
        base = level + trend * _damped_trend_sum(phi, h)
        out[h - 1] = base + s if seasonal == "add" else base * s
    return np.clip(out, 0, None)


# ------------------------------------------------------------ 多元线性回归


def _design_matrix(feat: pd.DataFrame, t: np.ndarray) -> np.ndarray:
    """构造回归设计矩阵：截距 + 趋势 + 小时哑变量 + 星期哑变量 + 高峰/节假日/雨天。"""
    n = len(feat)
    cols: List[np.ndarray] = [np.ones(n), np.asarray(t, dtype=float)]
    hour = feat["hour"].to_numpy()
    for k in range(1, 24):
        cols.append((hour == k).astype(float))
    weekday = feat["weekday"].to_numpy()
    for k in range(1, 7):
        cols.append((weekday == k).astype(float))
    for name in ("is_peak", "is_holiday", "rain"):
        cols.append(feat[name].to_numpy(dtype=float))
    return np.column_stack(cols)


def linear_regression_forecast(
    y_train: np.ndarray,
    feat_train: pd.DataFrame,
    feat_target: pd.DataFrame,
    t_train: np.ndarray,
    t_target: np.ndarray,
) -> np.ndarray:
    """最小二乘多元线性回归直接多步预测。"""
    X_train = _design_matrix(feat_train, t_train)
    X_target = _design_matrix(feat_target, t_target)
    beta, *_ = np.linalg.lstsq(X_train, np.asarray(y_train, dtype=float), rcond=None)
    return np.clip(X_target @ beta, 0, None)


# --------------------------------------------------------------------------
# 二、滚动原点回测与自动选型
# --------------------------------------------------------------------------


def _predict(
    name: str,
    train: pd.Series,
    target_index: pd.DatetimeIndex,
    train_feat: pd.DataFrame,
    target_feat: pd.DataFrame,
    t_train: np.ndarray,
    t_target: np.ndarray,
) -> np.ndarray:
    """按模型名分发到具体算法（全部为直接多步预测）。"""
    horizon = len(target_index)
    if name == "mean_baseline":
        return mean_baseline_forecast(train, horizon)
    if name == "seasonal_naive":
        lag = settings.FORECAST_SEASONAL_LAG
        if lag < horizon:
            lag = int(math.ceil(horizon / 24.0) * 24)
        return seasonal_naive_forecast(train, target_index, lag_hours=lag)
    if name == "moving_average":
        period = settings.FORECAST_SEASONAL_LAG
        if period < horizon:
            period = int(math.ceil(horizon / 24.0) * 24)
        return moving_average_forecast(train, target_index, period=period, weeks=3)
    if name == "holt_winters":
        use_period = WEEK_HOURS if len(train) >= 2 * WEEK_HOURS else 24
        return holt_winters_forecast(train, horizon, period=use_period)
    if name == "linear_regression":
        return linear_regression_forecast(
            train.to_numpy(dtype=float), train_feat, target_feat, t_train, t_target
        )
    raise ValueError(f"未知模型: {name}")


def _ensemble_weights(metrics: Dict[str, Dict], key: str = "rmse") -> Dict[str, float]:
    """按回测误差倒数计算组合权重（误差越小权重越大）。"""
    weights: Dict[str, float] = {}
    for name, met in metrics.items():
        value = met.get(key)
        if value is None:
            value = met.get("mae") or 1.0
        weights[name] = 1.0 / (float(value) + 1e-6)
    return weights


def rolling_backtest(
    series: pd.Series,
    features: pd.DataFrame,
    valid_hours: int,
    model_names: Sequence[str],
    n_folds: int = 3,
) -> Dict:
    """滚动原点回测：每折以历史末端为原点，直接预测未来 ``valid_hours`` 小时。

    :return: ``{model: {"metrics": ..., "preds": [...], "actuals": [...]}}``
    """
    n = len(series)
    n_folds = max(1, int(n_folds))
    folds = []
    for f in range(1, n_folds + 1):
        test_end = n - valid_hours * (f - 1)
        test_start = n - valid_hours * f
        if test_start < WEEK_HOURS * 2:  # 训练集不足两周则不再向前滚动
            break
        folds.append((test_start, test_end))
    if not folds:
        folds = [(max(WEEK_HOURS * 2, n - valid_hours), n)]

    requested = [m for m in model_names if m in MODEL_LABELS and m != "ensemble"]
    collected: Dict[str, Dict[str, list]] = {
        m: {"preds": [], "actuals": []} for m in requested
    }

    for test_start, test_end in folds:
        train = series.iloc[:test_start]
        test = series.iloc[test_start:test_end]
        train_feat = features.iloc[:test_start]
        test_feat = features.iloc[test_start:test_end]
        t_train = np.arange(len(train), dtype=float)
        t_target = np.arange(test_start, test_end, dtype=float)
        for name in requested:
            try:
                pred = _predict(
                    name, train, test.index, train_feat, test_feat, t_train, t_target
                )
            except Exception:
                continue
            collected[name]["preds"].append(np.asarray(pred, dtype=float))
            collected[name]["actuals"].append(test.to_numpy(dtype=float))

    output: Dict[str, Dict] = {}
    for name, data in collected.items():
        if not data["preds"]:
            continue
        preds = np.concatenate(data["preds"])
        actuals = np.concatenate(data["actuals"])
        output[name] = {
            "metrics": compute_metrics(actuals, preds),
            "preds": preds,
            "actuals": actuals,
        }
    if not output:
        raise ValueError("没有可用的预测模型，请检查历史数据量")
    return output


def backtest_and_forecast(
    series: pd.Series,
    features: pd.DataFrame,
    horizon: int,
    valid_hours: int,
    model_names: Sequence[str],
    auto_select: bool = True,
    n_folds: Optional[int] = None,
) -> Dict:
    """回测评估所有模型 → 自动选优 → 用最优模型预测未来 ``horizon`` 小时。

    :param series: 连续的按小时需求序列（DatetimeIndex）
    :param features: 与 series 同索引的特征矩阵
    :param valid_hours: 每折回测的预测步长（小时）
    :param auto_select: False 时按 model_names 顺序取第一个可用模型
    """
    n_folds = n_folds or settings.FORECAST_FOLDS
    requested = [m for m in model_names if m in MODEL_LABELS]

    # 基线模型只参与评估展示，不参与选优
    backtest = rolling_backtest(
        series, features, valid_hours, requested, n_folds=n_folds
    )

    # ---------------- 组合模型：逆误差加权 ----------------
    # 权重只由真正参与竞争的可选模型决定；均值基线仅作参照，不能进入组合
    key = settings.FORECAST_SELECT_METRIC
    weights = _ensemble_weights(
        {m: d["metrics"] for m, d in backtest.items() if m in SELECTABLE_MODELS}, key
    )
    if "ensemble" in requested and len(backtest) > 1:
        names = [m for m in backtest if m in SELECTABLE_MODELS]
        if len(names) > 1:
            actuals = backtest[names[0]]["actuals"]
            w = np.array([weights[m] for m in names], dtype=float)
            w = w / w.sum()
            stacked = np.vstack([backtest[m]["preds"] for m in names])
            ensemble_pred = w @ stacked
            backtest["ensemble"] = {
                "metrics": compute_metrics(actuals, ensemble_pred),
                "preds": ensemble_pred,
                "actuals": actuals,
            }

    # ---------------- 选优（主指标） ----------------
    def score(name: str) -> float:
        value = backtest[name]["metrics"].get(key)
        return float("inf") if value is None else float(value)

    candidates = [m for m in backtest if m in SELECTABLE_MODELS]
    if not candidates:
        raise ValueError("没有可参与选优的模型")
    best = min(candidates, key=score)
    if not auto_select:
        for name in requested:
            if name in candidates:
                best = name
                break

    # ---------------- 全量重训 + 未来预测 ----------------
    last_ts = series.index[-1]
    target_index = pd.date_range(last_ts + pd.Timedelta(hours=1), periods=horizon, freq="h")
    target_feat = build_features(target_index)
    t_full = np.arange(len(series), dtype=float)
    t_future = np.arange(len(series), len(series) + horizon, dtype=float)

    full_preds: Dict[str, np.ndarray] = {}
    for name in candidates:
        if name in ("ensemble", "mean_baseline"):
            continue
        try:
            full_preds[name] = _predict(
                name, series, target_index, features, target_feat, t_full, t_future
            )
        except Exception:
            continue

    if best == "ensemble" and full_preds:
        w = np.array([weights[m] for m in full_preds], dtype=float)
        w = w / w.sum()
        future = w @ np.vstack([full_preds[m] for m in full_preds])
    elif best in full_preds:
        future = full_preds[best]
    elif full_preds:
        best = next(iter(full_preds))
        future = full_preds[best]
    else:
        best = "mean_baseline"
        future = mean_baseline_forecast(series, horizon)

    # ---------------- 置信区间（基于回测残差） ----------------
    residual = backtest[best]["actuals"] - backtest[best]["preds"]
    sigma = float(np.std(residual)) if len(residual) else 0.0
    widen = 1.96 * sigma * (1 + 0.01 * np.arange(1, horizon + 1))
    lower = np.clip(future - widen, 0, None)
    upper = future + widen

    metric_list = []
    for name, data in backtest.items():
        metric_list.append(
            {
                "model": name,
                "model_label": MODEL_LABELS.get(name, name),
                **data["metrics"],
                "is_best": name == best,
            }
        )
    metric_list.sort(key=lambda item: (item[key] is None, item[key]))

    return {
        "model": best,
        "model_label": MODEL_LABELS.get(best, best),
        "metrics": metric_list,
        "weights": weights,
        "select_metric": key,
        "folds": n_folds,
        "points": [
            {
                "time": ts.to_pydatetime(),
                "value": round(float(v), 2),
                "lower": round(float(lo), 2),
                "upper": round(float(up), 2),
            }
            for ts, v, lo, up in zip(target_index, future, lower, upper)
        ],
        "valid_hours": valid_hours,
    }


# --------------------------------------------------------------------------
# 三、数据访问层
# --------------------------------------------------------------------------


def load_hourly_demand(
    db: Session,
    region_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """从 ride_request 聚合出等间隔小时需求序列。

    :return: 以小时为索引的 DataFrame，列包含 demand / is_holiday / rain
    """
    start, end = _date_range(start_date, end_date, default_days=settings.FORECAST_MAX_HISTORY_DAYS)
    lo, hi = datetime_bounds(start, end)

    rain_expr = func.max(
        case((models.RideRequest.weather.in_(RAINY_WEATHER), 1), else_=0)
    ).label("rain")
    holiday_expr = func.max(
        case((models.RideRequest.is_holiday.is_(True), 1), else_=0)
    ).label("holiday")

    query = db.query(
        models.RideRequest.stat_date.label("stat_date"),
        models.RideRequest.hour.label("hour"),
        func.count(models.RideRequest.id).label("demand"),
        rain_expr,
        holiday_expr,
    ).filter(
        models.RideRequest.request_time >= lo,
        models.RideRequest.request_time < hi,
    )
    if region_id:
        query = query.filter(models.RideRequest.region_id == region_id)
    rows = query.group_by(models.RideRequest.stat_date, models.RideRequest.hour).all()

    if not rows:
        return pd.DataFrame(columns=["demand", "is_holiday", "rain"])

    frame = pd.DataFrame(
        [
            {
                "time": datetime.combine(r.stat_date, datetime.min.time())
                + timedelta(hours=int(r.hour)),
                "demand": float(r.demand or 0),
                "rain": float(r.rain or 0),
                "is_holiday": float(r.holiday or 0),
            }
            for r in rows
        ]
    )
    frame = frame.set_index("time").sort_index()

    full_index = pd.date_range(frame.index.min(), frame.index.max(), freq="h")
    frame = frame.reindex(full_index)
    frame["demand"] = frame["demand"].fillna(0.0)
    frame["rain"] = frame["rain"].fillna(0.0)
    frame["is_holiday"] = frame["is_holiday"].fillna(0.0)
    return frame


def forecast_region(
    db: Session,
    region_id: Optional[int] = None,
    horizon: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    model_names: Optional[Iterable[str]] = None,
    auto_select: bool = True,
    persist: bool = True,
    created_by: Optional[str] = None,
) -> Dict:
    """对指定区域（或全域）执行需求预测。"""
    horizon = int(horizon or settings.FORECAST_HORIZON)
    frame = load_hourly_demand(db, region_id, start_date, end_date)
    if frame.empty:
        raise ValueError("暂无历史叫车需求数据，请先导入或生成运营数据")

    history_days = len(frame) / 24.0
    if history_days < settings.FORECAST_MIN_HISTORY_DAYS:
        raise ValueError(
            f"历史数据仅 {history_days:.1f} 天，不足 {settings.FORECAST_MIN_HISTORY_DAYS} 天，无法可靠建模"
        )

    series = frame["demand"].astype(float)
    series.index = pd.to_datetime(series.index)
    holidays = {ts.date() for ts in series.index[frame["is_holiday"] > 0]}
    rain_hours = {
        ts.to_pydatetime().replace(minute=0, second=0, microsecond=0)
        for ts in series.index[frame["rain"] > 0]
    }
    features = build_features(series.index, holidays, rain_hours)

    models_to_use = list(model_names) if model_names else list(settings.FORECAST_MODELS)
    result = backtest_and_forecast(
        series,
        features,
        horizon=horizon,
        valid_hours=max(settings.FORECAST_VALID_HOURS, horizon),
        model_names=models_to_use,
        auto_select=auto_select,
    )

    region_name = "全域"
    if region_id:
        region = db.get(models.Region, region_id)
        region_name = region.name if region else f"区域{region_id}"

    tail = series.iloc[-24 * 7:]
    history = [
        {"time": ts.to_pydatetime(), "value": round(float(v), 2), "lower": 0, "upper": 0}
        for ts, v in tail.items()
    ]

    batch_no = f"FC{datetime.now().strftime('%Y%m%d%H%M%S')}{np.random.randint(100, 999)}"
    payload = {
        "region_id": region_id,
        "region_name": region_name,
        "model": result["model"],
        "model_label": result["model_label"],
        "horizon": horizon,
        "history_days": int(history_days),
        "generated_at": datetime.now(),
        "batch_no": batch_no,
        "metrics": result["metrics"],
        "points": result["points"],
        "history": history,
        "valid_hours": result["valid_hours"],
        "select_metric": result["select_metric"],
        "folds": result["folds"],
    }

    if persist:
        _save_forecast(db, payload, created_by)
    return payload


def _save_forecast(db: Session, payload: Dict, created_by: Optional[str]) -> None:
    """保存预测结果，供后续准确率评估。"""
    best_mape = next(
        (m.get("mape") for m in payload["metrics"] if m["model"] == payload["model"]), None
    )
    rows = [
        models.ForecastResult(
            batch_no=payload["batch_no"],
            region_id=payload["region_id"],
            target_time=point["time"],
            target_date=point["time"].date(),
            hour=point["time"].hour,
            model_name=payload["model"],
            predicted_value=point["value"],
            lower_bound=point["lower"],
            upper_bound=point["upper"],
            mape=best_mape,
            horizon=payload["horizon"],
            created_by=created_by,
        )
        for point in payload["points"]
    ]
    db.bulk_save_objects(rows)
    db.commit()


def backfill_actual(db: Session) -> int:
    """把已经过去的预测点回填真实需求值，用于计算预测准确率。"""
    now = datetime.now()
    pending = (
        db.query(models.ForecastResult)
        .filter(
            models.ForecastResult.target_time < now,
            models.ForecastResult.actual_value.is_(None),
        )
        .limit(5000)
        .all()
    )
    if not pending:
        return 0

    min_time = min(p.target_time for p in pending)
    max_time = max(p.target_time for p in pending)
    query = db.query(
        models.RideRequest.region_id,
        models.RideRequest.stat_date,
        models.RideRequest.hour,
        func.count(models.RideRequest.id),
    ).filter(
        models.RideRequest.request_time >= min_time - timedelta(hours=1),
        models.RideRequest.request_time < max_time + timedelta(hours=2),
    )
    actual_map = {}
    total_map = {}
    for region_id, stat_date, hour, cnt in query.group_by(
        models.RideRequest.region_id, models.RideRequest.stat_date, models.RideRequest.hour
    ):
        actual_map[(region_id, stat_date, int(hour))] = float(cnt)
        total_map[(stat_date, int(hour))] = total_map.get((stat_date, int(hour)), 0.0) + float(cnt)

    updated = 0
    for item in pending:
        key = (item.region_id, item.target_date, int(item.hour))
        value = actual_map.get(key) if item.region_id else total_map.get((item.target_date, int(item.hour)))
        item.actual_value = 0.0 if value is None else value
        updated += 1
    db.commit()
    return updated


def forecast_accuracy(db: Session, days: int = 7) -> List[Dict]:
    """统计最近若干天已回填真实值的预测准确率（按模型汇总）。"""
    backfill_actual(db)
    since = datetime.now() - timedelta(days=days)
    rows = (
        db.query(
            models.ForecastResult.model_name,
            models.ForecastResult.predicted_value,
            models.ForecastResult.actual_value,
        )
        .filter(
            models.ForecastResult.create_time >= since,
            models.ForecastResult.actual_value.isnot(None),
        )
        .all()
    )
    buckets: Dict[str, List[Tuple[float, float]]] = {}
    for model_name, pred, actual in rows:
        buckets.setdefault(model_name, []).append((float(pred), float(actual)))

    output = []
    for model_name, pairs in buckets.items():
        pred = np.array([p for p, _ in pairs], dtype=float)
        actual = np.array([a for _, a in pairs], dtype=float)
        met = compute_metrics(actual, pred)
        mape = met.get("mape")
        output.append(
            {
                "model_label": MODEL_LABELS.get(model_name, model_name),
                "sample_count": len(pairs),
                "mae": met["mae"],
                "rmse": met["rmse"],
                "mape": mape,
                "accuracy": None if mape is None else round(max(0.0, 100 - mape), 2),
            }
        )
    output.sort(key=lambda item: (item["mape"] is None, item["mape"]))
    return output
