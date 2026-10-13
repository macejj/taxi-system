"""调度决策引擎单元测试（纯算法部分）。

不依赖 pytest，可直接运行：  python tests/test_dispatch.py
"""
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.dispatch import (  # noqa: E402
    greedy_assignment,
    haversine_km,
    hungarian_max_weight,
    road_distance_km,
)

from app.config import settings  # noqa: E402


def total_gain(matrix, pairs):
    return float(sum(matrix[i][j] for i, j in pairs))


def brute_force_max(matrix):
    """穷举法求最大权匹配（仅用于小规模验证）。"""
    n, m = matrix.shape
    best = 0.0
    # 枚举行的一个子集到列的一个单射
    for k in range(0, min(n, m) + 1):
        for rows in itertools.permutations(range(n), k):
            for cols in itertools.permutations(range(m), k):
                value = sum(matrix[i][j] for i, j in zip(rows, cols))
                best = max(best, value)
    return best


def test_haversine():
    # 北京天安门 -> 北京南站 约 6 公里
    d = haversine_km(116.397, 39.909, 116.378, 39.865)
    assert 4.0 < d < 7.0, d
    # 同一点距离为 0
    assert haversine_km(116.4, 39.9, 116.4, 39.9) < 1e-9
    assert road_distance_km(116.397, 39.909, 116.378, 39.865) > d
    print("  [OK] haversine / road_distance")


def test_hungarian_optimality():
    """匈牙利算法结果必须等于穷举最优解。"""
    rng = np.random.default_rng(7)
    for trial in range(20):
        n = int(rng.integers(2, 5))
        m = int(rng.integers(2, 5))
        matrix = np.round(rng.uniform(-5, 20, size=(n, m)), 2)
        pairs = hungarian_max_weight(matrix)
        got = total_gain(matrix, pairs)
        expect = brute_force_max(matrix)
        assert abs(got - expect) < 1e-6, (trial, matrix, got, expect)
        # 匹配必须是单射
        rows = [i for i, _ in pairs]
        cols = [j for _, j in pairs]
        assert len(set(rows)) == len(rows) and len(set(cols)) == len(cols)
    print("  [OK] hungarian 与穷举最优解一致（20 组随机矩阵）")


def test_hungarian_vs_greedy():
    """匈牙利算法总收益不低于贪心策略。"""
    rng = np.random.default_rng(2024)
    better = 0
    for _ in range(30):
        n, m = 12, 12
        matrix = np.round(rng.uniform(-10, 30, size=(n, m)), 2)
        h = total_gain(matrix, hungarian_max_weight(matrix))
        g = total_gain(matrix, greedy_assignment(matrix))
        assert h >= g - 1e-6, (h, g)
        if h > g + 1e-9:
            better += 1
    assert better > 0, "匈牙利算法在任何测试中都没有优于贪心，疑似实现有误"
    print(f"  [OK] hungarian >= greedy（30 组中有 {better} 组严格更优）")


def test_assignment_edge_cases():
    assert hungarian_max_weight([]) == []
    assert hungarian_max_weight([[]]) == []
    assert greedy_assignment([]) == []
    # 全负收益 -> 不应产生任何调度
    neg = np.full((3, 3), -5.0)
    assert hungarian_max_weight(neg) == []
    assert greedy_assignment(neg) == []
    # 收益为 0 -> 也不调度
    zero = np.zeros((3, 3))
    assert hungarian_max_weight(zero) == []
    print("  [OK] 边界情形（空矩阵/全负收益/零收益）")


def test_realistic_scenario():
    """构造一个真实的供需场景，检验调度方案是否符合直觉。"""
    from app.services.dispatch import RegionState, build_gain_matrix, solve_assignment

    states = [
        RegionState(1, "老城区", "居民区", 116.40, 39.90, predicted_demand=60, current_supply=70),
        RegionState(2, "高铁站", "交通枢纽", 116.43, 39.91, predicted_demand=95, current_supply=20),
        RegionState(3, "科技园", "商圈", 116.46, 39.92, predicted_demand=80, current_supply=30),
    ]
    for s in states:
        s.avg_amount = 25.0
        s.effective_supply = s.current_supply * settings.VEHICLE_SERVICE_RATE
        s.gap = s.predicted_demand - s.effective_supply
        if s.gap < 0:
            s.movable_out = min(int(-s.gap / settings.VEHICLE_SERVICE_RATE), settings.DISPATCH_MAX_MOVE_OUT)
        else:
            s.needed_in = min(int(np.ceil(s.gap / settings.VEHICLE_SERVICE_RATE)), settings.DISPATCH_MAX_MOVE_PER_REGION)

    vehicles = [(101, 0, 116.40, 39.90), (102, 0, 116.40, 39.90), (103, 0, 116.40, 39.90)]
    matrix, slots, detail = build_gain_matrix(states, vehicles)
    assert matrix.shape[0] == 3 and matrix.shape[1] > 0
    pairs = solve_assignment(matrix, "hungarian")
    assert len(pairs) > 0
    # 所有调度都应指向缺口区域（下标 1 或 2），而不是盈余区域（下标 0）
    for i, j in pairs:
        to_idx = slots[j][0]
        assert to_idx in (1, 2), (i, j, to_idx)
    print(f"  [OK] 真实场景调度：{len(pairs)} 辆车从盈余区调往缺口区，"
          f"预期净收益 {total_gain(matrix, pairs):.2f} 元")


if __name__ == "__main__":
    print("=== 调度决策引擎自检 ===")
    test_haversine()
    test_assignment_edge_cases()
    test_hungarian_optimality()
    test_hungarian_vs_greedy()
    test_realistic_scenario()
    print("=== 全部通过 ===")
