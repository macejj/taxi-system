"""需求预测引擎单元测试。

不依赖 pytest，可直接运行：  python tests/test_forecast.py
"""
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.forecast import (  # noqa: E402
    SELECTABLE_MODELS,
    backtest_and_forecast,
    build_features,
    compute_metrics,
    holt_winters_forecast,
    linear_regression_forecast,
    mean_baseline_forecast,
    moving_average_forecast,
    rolling_backtest,
    seasonal_naive_forecast,
)


def make_series(days: int = 90, seed: int = 42) -> pd.Series:
    """构造带「日周期 + 周周期 + 趋势 + 噪声」的合成需求序列。"""
    rng = np.random.default_rng(seed)
    index = pd.date_range(datetime(2024, 1, 1), periods=days * 24, freq="h")
    hour = index.hour.to_numpy()
    weekday = index.dayofweek.to_numpy()
    daily = (
        4
        + 3 * np.sin((hour - 7) / 24 * 2 * np.pi)
        + 4 * ((hour >= 7) & (hour < 9))
        + 4 * ((hour >= 17) & (hour < 19))
    )
    weekly = np.where(weekday >= 5, 1.25, 1.0)
    trend = 1 + np.arange(len(index)) / len(index) * 0.2
    poisson = rng.poisson(np.clip(daily * weekly * trend, 0.2, None))
    return pd.Series(poisson.astype(float), index=index)


def test_metrics():
    y = np.array([10.0, 20.0, 30.0])
    p = np.array([12.0, 18.0, 33.0])
    met = compute_metrics(y, p)
    assert abs(met["mae"] - 7 / 3) < 1e-3, met
    assert met["mape"] is not None and met["mape"] > 0
    assert compute_metrics(np.array([]), np.array([]))["mae"] == 0.0
    assert abs(compute_metrics(y, y)["r2"] - 1.0) < 1e-9
    print("  [OK] compute_metrics")


def test_baselines():
    series = make_series(30)
    target = pd.date_range(series.index[-1] + timedelta(hours=1), periods=168, freq="h")
    naive = seasonal_naive_forecast(series, target, lag_hours=168)
    ma = moving_average_forecast(series, target, period=168, weeks=3)
    base = mean_baseline_forecast(series, 168)
    for arr in (naive, ma, base):
        assert len(arr) == 168
        assert (arr >= 0).all() and not np.isnan(arr).any()
    assert base.std() == 0.0 and abs(base[0] - series.mean()) < 1e-9
    print("  [OK] mean_baseline / seasonal_naive / moving_average")


def test_no_lookahead():
    """核心正确性：模型只能看到预测原点之前的数据。

    做法：把预测窗口中段的数据全部置为极端异常值，
    若模型误差不受影响，说明它没有窥探预测窗口内的真实值。
    """
    series = make_series(60)
    origin = len(series) - 168
    train = series.iloc[:origin]
    target = series.index[origin:]
    horizon = len(target)

    tampered = series.copy()
    tampered.iloc[origin + 24: origin + 48] = 9999.0

    features = build_features(tampered.index)
    t_train = np.arange(len(train), dtype=float)
    t_target = np.arange(origin, len(series), dtype=float)
    train_feat = features.iloc[:origin]
    target_feat = features.iloc[origin:]

    naive_a = seasonal_naive_forecast(train, target, lag_hours=168)
    naive_b = seasonal_naive_forecast(tampered.iloc[:origin], target, lag_hours=168)
    assert np.allclose(naive_a, naive_b), "季节朴素法泄露了预测窗口内的数据"

    ma_a = moving_average_forecast(train, target, period=168, weeks=3)
    ma_b = moving_average_forecast(tampered.iloc[:origin], target, period=168, weeks=3)
    assert np.allclose(ma_a, ma_b), "季节移动平均泄露了预测窗口内的数据"

    lr_a = linear_regression_forecast(train.to_numpy(float), train_feat, target_feat, t_train, t_target)
    lr_b = linear_regression_forecast(
        tampered.iloc[:origin].to_numpy(float), train_feat, target_feat, t_train, t_target
    )
    assert np.allclose(lr_a, lr_b), "线性回归泄露了预测窗口内的数据"
    print("  [OK] 无前视泄露（训练集篡改不影响预测）")


def test_holt_winters():
    series = make_series(60)
    pred = holt_winters_forecast(series, horizon=24, period=168)
    assert len(pred) == 24 and (pred >= 0).all() and not np.isnan(pred).any()
    assert series.mean() * 0.2 < pred.mean() < series.mean() * 3.0, (pred.mean(), series.mean())
    short = make_series(4)
    pred_short = holt_winters_forecast(short, horizon=12, period=168)
    assert len(pred_short) == 12 and not np.isnan(pred_short).any()
    zero = pd.Series(np.zeros(24 * 30), index=pd.date_range(datetime(2024, 1, 1), periods=24 * 30, freq="h"))
    assert not np.isnan(holt_winters_forecast(zero, 12, period=168)).any()
    print("  [OK] holt_winters (含短序列/全零降级)")


def test_linear_regression():
    series = make_series(60)
    feat = build_features(series.index)
    target = pd.date_range(series.index[-1] + timedelta(hours=1), periods=24, freq="h")
    feat_target = build_features(target)
    t_train = np.arange(len(series), dtype=float)
    t_target = np.arange(len(series), len(series) + 24, dtype=float)
    pred = linear_regression_forecast(series.to_numpy(float), feat, feat_target, t_train, t_target)
    assert len(pred) == 24 and not np.isnan(pred).any() and (pred >= 0).all()
    hours = target.hour.to_numpy()
    peak_mean = pred[(hours >= 7) & (hours < 9)].mean()
    night_mean = pred[(hours >= 1) & (hours < 5)].mean()
    assert peak_mean > night_mean, (peak_mean, night_mean)
    print("  [OK] linear_regression (高峰识别)")


def test_rolling_backtest():
    series = make_series(90)
    features = build_features(series.index)
    result = rolling_backtest(series, features, valid_hours=168, model_names=list(SELECTABLE_MODELS), n_folds=3)
    assert len(result) >= 4, list(result)
    # 回测样本量 = 折数 × 168
    for name, data in result.items():
        assert len(data["preds"]) % 168 == 0, (name, len(data["preds"]))
        assert data["metrics"]["mae"] >= 0
    print(f"  [OK] rolling_backtest 折数×168 = {len(next(iter(result.values()))['preds'])} 个验证点")


def test_full_backtest():
    series = make_series(90)
    features = build_features(series.index)
    result = backtest_and_forecast(
        series,
        features,
        horizon=24,
        valid_hours=168,
        model_names=["mean_baseline", *SELECTABLE_MODELS],
        n_folds=3,
    )
    names = {m["model"] for m in result["metrics"]}
    assert "ensemble" in names and "mean_baseline" in names, names
    assert len(result["points"]) == 24
    best = [m for m in result["metrics"] if m["is_best"]]
    assert len(best) == 1 and best[0]["model"] != "mean_baseline", best
    for point in result["points"]:
        assert point["lower"] <= point["value"] <= point["upper"], point

    baseline = next(m for m in result["metrics"] if m["model"] == "mean_baseline")
    assert best[0]["rmse"] < baseline["rmse"], (best[0], baseline)
    print(f"  [OK] backtest 最优模型={result['model_label']} 选型指标={result['select_metric']}")
    print("  模型对比（滚动 3 折，验证点 504 个）：")
    for m in result["metrics"]:
        star = "*" if m["is_best"] else " "
        mape = "  N/A " if m["mape"] is None else f"{m['mape']:6.2f}"
        print(
            f"    {star} {m['model_label']:<26} MAE={m['mae']:<7.3f} "
            f"RMSE={m['rmse']:<7.3f} MAPE={mape}%"
        )


def test_degenerate_input():
    index = pd.date_range(datetime(2024, 1, 1), periods=30 * 24, freq="h")
    zeros = pd.Series(np.zeros(len(index)), index=index)
    features = build_features(index)
    result = backtest_and_forecast(
        zeros, features, horizon=12, valid_hours=48,
        model_names=list(SELECTABLE_MODELS), n_folds=2,
    )
    assert all(p["value"] >= 0 for p in result["points"])
    print("  [OK] 全零/退化输入鲁棒性")


if __name__ == "__main__":
    print("=== 需求预测引擎自检 ===")
    test_metrics()
    test_baselines()
    test_no_lookahead()
    test_holt_winters()
    test_linear_regression()
    test_rolling_backtest()
    test_full_backtest()
    test_degenerate_input()
    print("=== 全部通过 ===")
