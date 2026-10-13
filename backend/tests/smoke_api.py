"""接口冒烟测试：逐个调用后端接口，验证返回结构是否正确。

前置条件：后端已启动（默认 http://127.0.0.1:8000）。
用法：
    python tests/smoke_api.py
    python tests/smoke_api.py --base http://127.0.0.1:8000 --user admin --password admin123
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

PASSED: List[str] = []
FAILED: List[Tuple[str, str]] = []


def call(
    base: str,
    method: str,
    path: str,
    token: Optional[str] = None,
    body: Any = None,
    params: Optional[Dict] = None,
    timeout: int = 180,
) -> Tuple[int, Any]:
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            try:
                return response.status, json.loads(raw)
            except json.JSONDecodeError:
                return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw


def check(name: str, condition: bool, detail: str = "") -> bool:
    if condition:
        PASSED.append(name)
        print(f"  [PASS] {name}")
    else:
        FAILED.append((name, detail))
        print(f"  [FAIL] {name}  {detail}")
    return condition


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin123")
    args = parser.parse_args()
    base = args.base

    # ---------------------------------------------------------------- 认证
    section("认证")
    status, data = call(base, "POST", "/api/auth/login", body={"username": args.user, "password": args.password})
    if not check("登录", status == 200 and isinstance(data, dict) and "access_token" in data, str(data)[:200]):
        print("登录失败，终止测试")
        return 1
    token = data["access_token"]

    status, data = call(base, "POST", "/api/auth/login", body={"username": args.user, "password": "wrong-password"})
    check("错误密码被拒绝", status == 400, f"status={status}")

    status, data = call(base, "GET", "/api/auth/me", token=token)
    check("获取当前用户", status == 200 and data.get("username") == args.user, str(data)[:200])

    status, data = call(base, "GET", "/api/auth/me")
    check("未登录访问被拒绝", status == 401, f"status={status}")

    # ---------------------------------------------------------------- 驾驶舱
    section("驾驶舱")
    status, summary = call(base, "GET", "/api/dashboard/summary", token=token)
    check(
        "驾驶舱总览",
        status == 200 and "today" in summary and "fleet" in summary and "realtime" in summary,
        str(summary)[:200],
    )
    if status == 200:
        print(f"        今日订单 {summary['today']['order_count']} 单，"
              f"收入 {summary['today']['income']} 元，"
              f"在营车辆 {summary['fleet']['vehicle_active']} 台")

    status, trend = call(base, "GET", "/api/dashboard/trend", token=token, params={"days": 14})
    check("驾驶舱趋势", status == 200 and len(trend.get("income", [])) > 0, str(trend)[:200])

    status, alerts = call(base, "GET", "/api/dashboard/alerts", token=token)
    check("驾驶舱预警", status == 200 and "total" in alerts and "items" in alerts, str(alerts)[:200])
    if status == 200:
        print(f"        预警共 {alerts['total']} 条")
        for item in alerts["items"][:3]:
            print(f"          · [{item['level']}] {item['title']}")

    status, health = call(base, "GET", "/api/dashboard/health", token=token)
    check("数据健康度", status == 200 and health.get("counts", {}).get("operation_record", 0) > 0, str(health)[:200])

    # ---------------------------------------------------------------- 基础档案
    section("基础档案")
    status, regions = call(base, "GET", "/api/region/", token=token, params={"page": 1, "page_size": 50})
    check("区域分页列表", status == 200 and regions.get("total", 0) > 0, str(regions)[:200])
    region_id = regions["items"][0]["id"] if status == 200 and regions.get("items") else None

    status, all_regions = call(base, "GET", "/api/region/all", token=token)
    check("区域下拉列表", status == 200 and len(all_regions) > 0, str(all_regions)[:120])

    status, types = call(base, "GET", "/api/region/types", token=token)
    check("区域类型字典", status == 200 and len(types) > 0, str(types)[:120])

    status, vehicles = call(base, "GET", "/api/vehicle/", token=token, params={"page": 1, "page_size": 5})
    ok = status == 200 and vehicles.get("total", 0) > 0 and vehicles["items"][0].get("home_region_name")
    check("车辆列表（含关联信息）", ok, str(vehicles)[:250])
    if ok:
        sample = vehicles["items"][0]
        print(f"        {sample['plate_number']} {sample['brand_model']} "
              f"常驻{sample['home_region_name']} 绑定驾驶员={sample['bound_driver_name']}")

    status, drivers = call(base, "GET", "/api/driver/", token=token, params={"page": 1, "page_size": 5})
    ok = status == 200 and drivers.get("total", 0) > 0 and drivers["items"][0].get("home_region_name") is not None
    check("驾驶员列表（含关联信息）", ok, str(drivers)[:250])

    status, bindings = call(base, "GET", "/api/assignment/", token=token, params={"page": 1, "page_size": 5})
    ok = status == 200 and bindings.get("total", 0) > 0 and bindings["items"][0].get("plate_number")
    check("人车绑定列表", ok, str(bindings)[:250])

    status, dicts = call(base, "GET", "/api/vehicle/dictionaries", token=token)
    check("车辆字典", status == 200 and "vehicle_type" in dicts, str(dicts)[:150])

    # ---------------------------------------------------------------- 区域 CRUD
    section("区域增删改")
    code = f"T{int(time.time()) % 100000}"
    status, created = call(
        base, "POST", "/api/region/", token=token,
        body={"code": code, "name": "接口测试区", "region_type": "居民区",
              "center_lng": 113.6, "center_lat": 34.7, "area_km2": 5, "demand_level": 3, "status": 1},
    )
    ok = check("新增区域", status == 200 and created.get("code") == code, str(created)[:200])
    if ok:
        new_id = created["id"]
        status, dup = call(
            base, "POST", "/api/region/", token=token,
            body={"code": code, "name": "重复编码", "region_type": "居民区", "demand_level": 3, "status": 1},
        )
        check("重复编码被拒绝", status == 400, f"status={status}")

        status, updated = call(
            base, "PUT", f"/api/region/{new_id}", token=token,
            body={"code": code, "name": "接口测试区-已改名", "region_type": "商圈",
                  "center_lng": 113.6, "center_lat": 34.7, "area_km2": 6, "demand_level": 4, "status": 1},
        )
        check("修改区域", status == 200 and updated.get("name") == "接口测试区-已改名", str(updated)[:200])

        status, deleted = call(base, "DELETE", f"/api/region/{new_id}", token=token)
        check("删除区域", status == 200, str(deleted)[:150])

    if region_id:
        status, protected = call(base, "DELETE", f"/api/region/{region_id}", token=token)
        check("有关联数据的区域禁止删除", status == 400, f"status={status} {str(protected)[:150]}")

    # ---------------------------------------------------------------- 营运订单
    section("营运订单")
    status, ops = call(base, "GET", "/api/operation/", token=token, params={"page": 1, "page_size": 5})
    ok = status == 200 and ops.get("total", 0) > 0 and ops["items"][0].get("plate_number")
    check("订单分页列表（含关联名称）", ok, str(ops)[:250])

    status, op_summary = call(base, "GET", "/api/operation/summary", token=token, params={"start_date": None})
    check("订单汇总", status == 200 and op_summary.get("order_count", 0) > 0, str(op_summary)[:200])

    status, pays = call(base, "GET", "/api/operation/pay-types", token=token)
    check("支付方式字典", status == 200 and len(pays) > 0, str(pays)[:150])

    # 导出
    status, exported = call(base, "GET", "/api/operation/export/data", token=token, params={"fmt": "csv", "limit": 20})
    check("导出 CSV", status == 200 and isinstance(exported, str) and "订单号" in exported, str(exported)[:120])

    # ---------------------------------------------------------------- 需求数据
    section("叫车需求")
    status, reqs = call(base, "GET", "/api/demand/", token=token, params={"page": 1, "page_size": 5})
    ok = status == 200 and reqs.get("total", 0) > 0 and reqs["items"][0].get("region_name")
    check("需求分页列表", ok, str(reqs)[:250])

    status, dem_sum = call(base, "GET", "/api/demand/summary", token=token)
    check("需求汇总", status == 200 and dem_sum.get("request_count", 0) > 0, str(dem_sum)[:200])
    if status == 200:
        print(f"        近 7 天需求 {dem_sum['request_count']} 单，满足率 {dem_sum['fulfil_rate']}%")

    status, matrix = call(base, "GET", "/api/demand/region-hour-matrix", token=token)
    check("区域×小时需求矩阵", status == 200 and len(matrix.get("matrix", [])) > 0, str(matrix)[:150])

    status, wh = call(base, "GET", "/api/demand/weekday-hour", token=token)
    check("星期×小时需求分布", status == 200 and len(wh.get("matrix", [])) == 7, str(wh)[:150])

    # ---------------------------------------------------------------- 运营分析
    section("运营分析")
    analysis_cases = [
        ("KPI 总览", "/api/analysis/overview", {}, lambda d: "vs_prev" in d),
        ("收入趋势", "/api/analysis/income-trend", {"group_by": "day"}, lambda d: len(d) > 0),
        ("24小时分布", "/api/analysis/hourly-profile", {}, lambda d: len(d) == 24),
        ("星期分布", "/api/analysis/weekday-profile", {}, lambda d: len(d) == 7),
        ("热力图", "/api/analysis/heatmap", {}, lambda d: len(d.get("matrix", [])) == 7),
        ("区域排行", "/api/analysis/region-ranking", {}, lambda d: len(d) > 0),
        ("区域对比", "/api/analysis/region-compare", {}, lambda d: len(d.get("series", [])) > 0),
        ("里程利用率", "/api/analysis/load-rate", {}, lambda d: "load_rate" in d),
        ("驾驶员排行", "/api/analysis/driver-ranking", {"top_n": 5}, lambda d: len(d) > 0),
        ("车辆效率", "/api/analysis/vehicle-efficiency", {"top_n": 5}, lambda d: len(d) > 0),
        ("支付方式", "/api/analysis/pay-type", {}, lambda d: len(d) > 0),
        ("天气影响", "/api/analysis/weather-impact", {}, lambda d: len(d) > 0),
        ("异常预警", "/api/analysis/abnormal-alert", {}, lambda d: isinstance(d, list)),
        ("分析驾驶舱", "/api/analysis/dashboard", {}, lambda d: "kpi" in d and "hourly" in d),
    ]
    for name, path, params, validator in analysis_cases:
        status, data = call(base, "GET", path, token=token, params=params)
        ok = status == 200 and validator(data) if status == 200 else False
        check(name, ok, f"status={status} {str(data)[:180]}")

    status, ranking = call(base, "GET", "/api/analysis/region-ranking", token=token)
    if status == 200 and ranking:
        print("        区域收入排行前三：")
        for item in ranking[:3]:
            print(f"          · {item['region_name']}: {item['income']:.0f} 元 / "
                  f"{item['order_count']} 单 / 未满足率 {item['unfulfil_rate']}%")

    status, dr = call(base, "GET", "/api/analysis/driver-ranking", token=token, params={"top_n": 3})
    if status == 200 and dr:
        print("        驾驶员绩效前三：")
        for item in dr:
            print(f"          · {item['name']}: {item['income']:.0f} 元 / {item['order_count']} 单 / 评分 {item['rating']}")

    # ---------------------------------------------------------------- 需求预测
    section("需求预测")
    status, models_list = call(base, "GET", "/api/forecast/models", token=token)
    check("预测模型列表", status == 200 and len(models_list) >= 5, str(models_list)[:200])

    status, fc_regions = call(base, "GET", "/api/forecast/regions", token=token)
    check("可预测区域列表", status == 200 and len(fc_regions) > 1, str(fc_regions)[:200])
    target_region = None
    if status == 200:
        candidates = [r for r in fc_regions if r["region_id"] and r["request_count"] > 5000]
        target_region = candidates[0]["region_id"] if candidates else None

    print("        正在执行全域预测（含滚动回测，可能需要几十秒）...")
    started = time.time()
    status, fc = call(base, "POST", "/api/forecast/run", token=token,
                      body={"region_id": None, "horizon": 24, "auto_select": True})
    elapsed = time.time() - started
    ok = (
        status == 200
        and len(fc.get("points", [])) == 24
        and len(fc.get("metrics", [])) >= 5
    )
    check(f"全域预测（{elapsed:.1f}s）", ok, f"status={status} {str(fc)[:250]}")
    if ok:
        print(f"        最优模型：{fc['model_label']}  历史 {fc['history_days']} 天  "
              f"选型指标={fc.get('select_metric')}  回测折数={fc.get('folds')}")
        for metric in fc["metrics"]:
            star = "*" if metric["is_best"] else " "
            print(f"          {star} {metric['model_label']:<26} MAE={metric['mae']:<7.3f} "
                  f"RMSE={metric['rmse']:<7.3f} MAPE={metric['mape']}%")
        print("        未来 6 小时预测：")
        for point in fc["points"][:6]:
            print(f"          · {point['time']}  预测 {point['value']:.1f} 单 "
                  f"[{point['lower']:.1f}, {point['upper']:.1f}]")

    if target_region:
        print(f"        正在执行区域 {target_region} 预测 ...")
        status, fc2 = call(base, "POST", "/api/forecast/run", token=token,
                           body={"region_id": target_region, "horizon": 24})
        check("单区域预测", status == 200 and len(fc2.get("points", [])) == 24, f"status={status} {str(fc2)[:200]}")
        if status == 200:
            print(f"        {fc2['region_name']}：最优模型 {fc2['model_label']}，"
                  f"回测 MAPE={next(m['mape'] for m in fc2['metrics'] if m['is_best'])}%")

    status, acc = call(base, "GET", "/api/forecast/accuracy", token=token, params={"days": 30})
    check("预测准确率", status == 200 and isinstance(acc, list), str(acc)[:200])

    status, hist = call(base, "GET", "/api/forecast/history", token=token, params={"limit": 5})
    check("预测历史批次", status == 200 and len(hist) > 0, str(hist)[:200])
    if status == 200 and hist:
        batch = hist[0]["batch_no"]
        status, detail = call(base, "GET", f"/api/forecast/batch/{batch}", token=token)
        check("预测批次明细", status == 200 and len(detail) > 0, str(detail)[:150])

    # ---------------------------------------------------------------- 调度决策
    section("调度决策")
    status, rs = call(base, "GET", "/api/dispatch/region-status", token=token)
    ok = status == 200 and len(rs.get("items", [])) > 0
    check("区域供需态势", ok, f"status={status} {str(rs)[:250]}")
    if ok:
        print(f"        目标时段 {rs['target_date']} {rs['target_hour']:02d}:00")
        print(f"        需求估计方法：{rs['method']}")
        for item in rs["items"][:5]:
            print(f"          · {item['region_name']:<10} 需求{item['predicted_demand']:7.1f} "
                  f"运力{item['effective_supply']:6.1f} 缺口{item['gap']:7.1f}  {item['gap_level']}")

    status, plan = call(base, "POST", "/api/dispatch/generate", token=token,
                        body={"strategy": "hungarian", "auto_save": True})
    ok = status == 200 and plan.get("plan") is not None
    check("生成调度方案（匈牙利）", ok, f"status={status} {str(plan)[:300]}")
    plan_id = None
    if ok:
        p = plan["plan"]
        plan_id = p.get("id")
        print(f"        方案号 {p['plan_no']}  目标 {p['target_hour']:02d}:00  "
              f"调度 {p['dispatch_count']} 台  预期净收益 {p['expected_gain']} 元")
        print("        策略对比：")
        for item in plan["strategy_compare"]:
            print(f"          · {item['strategy_label']}: {item['dispatch_count']} 台，"
                  f"预期净收益 {item['expected_gain']} 元")
        for warning in plan.get("warnings", []):
            print(f"        ! {warning}")
        if p.get("orders"):
            print("        调度指令前 5 条：")
            for order in p["orders"][:5]:
                print(f"          · {order.get('from_region_name')} → {order.get('to_region_name')} "
                      f"距离{order['distance_km']}km 预期净收益{order['expected_gain']}元 "
                      f"优先级{order['priority']}")

    status, greedy = call(base, "POST", "/api/dispatch/generate", token=token,
                          body={"strategy": "greedy", "auto_save": False})
    ok = status == 200 and len(greedy.get("strategy_compare", [])) == 2
    check("贪心策略对比（不保存）", ok, f"status={status} {str(greedy)[:200]}")
    if ok:
        hungarian_gain = next(i["expected_gain"] for i in greedy["strategy_compare"] if i["strategy"] == "hungarian")
        greedy_gain = next(i["expected_gain"] for i in greedy["strategy_compare"] if i["strategy"] == "greedy")
        check("匈牙利不劣于贪心", hungarian_gain >= greedy_gain,
              f"hungarian={hungarian_gain} greedy={greedy_gain}")
        print(f"        匈牙利 {hungarian_gain} 元  vs  贪心 {greedy_gain} 元")

    status, plans = call(base, "GET", "/api/dispatch/plans", token=token, params={"page": 1, "page_size": 5})
    check("调度方案列表", status == 200 and plans.get("total", 0) > 0, str(plans)[:200])

    if plan_id:
        status, detail = call(base, "GET", f"/api/dispatch/plans/{plan_id}", token=token)
        check("调度方案详情", status == 200 and detail.get("orders") is not None, str(detail)[:200])

        status, orders = call(base, "GET", "/api/dispatch/orders", token=token,
                              params={"plan_id": plan_id, "page": 1, "page_size": 5})
        check("调度单列表", status == 200 and orders.get("total", 0) > 0, str(orders)[:200])

        if orders.get("items"):
            order_id = orders["items"][0]["id"]
            status, feedback = call(base, "POST", f"/api/dispatch/orders/{order_id}/feedback", token=token,
                                    body={"status": 2, "feedback": "接口测试：已按指令完成调度"})
            check("提交调度执行反馈", status == 200 and feedback.get("status") == 2, str(feedback)[:200])

        status, effect = call(base, "GET", f"/api/dispatch/plans/{plan_id}/effect", token=token)
        check("调度效果评估", status == 200 and "actual_gain" in effect, str(effect)[:250])
        if status == 200:
            print(f"        效果评估：调度 {effect['dispatch_count']} 台，完成 {effect['done_count']} 台，"
                  f"预期 {effect['expected_gain']} 元，实际 {effect['actual_gain']} 元")

    status, stats = call(base, "GET", "/api/dispatch/statistics", token=token, params={"days": 30})
    check("调度统计", status == 200 and "by_strategy" in stats, str(stats)[:200])

    # ---------------------------------------------------------------- 系统管理
    section("系统管理")
    status, users = call(base, "GET", "/api/system/users", token=token, params={"page": 1, "page_size": 10})
    check("用户列表（管理员）", status == 200 and users.get("total", 0) >= 1, str(users)[:200])

    status, configs = call(base, "GET", "/api/system/configs", token=token)
    check("参数配置列表", status == 200 and len(configs) > 10, str(configs)[:200])
    if status == 200:
        print(f"        共 {len(configs)} 项系统参数")
        for item in configs[:3]:
            print(f"          · {item['config_name']} = {item['config_value']} ({item['config_group']})")

        key = configs[0]["config_key"]
        old = configs[0]["config_value"]
        status, updated = call(base, "PUT", f"/api/system/configs/{key}", token=token,
                               body={"config_value": old})
        check("修改参数配置", status == 200, str(updated)[:150])

    status, reloaded = call(base, "POST", "/api/system/configs/reload", token=token)
    check("重新载入参数配置", status == 200, str(reloaded)[:150])

    status, logs = call(base, "GET", "/api/system/logs", token=token, params={"page": 1, "page_size": 5})
    check("操作日志", status == 200 and logs.get("total", 0) > 0, str(logs)[:200])
    if status == 200 and logs.get("items"):
        item = logs["items"][0]
        print(f"        最近日志：{item['username']} {item['method']} {item['path']} "
              f"→ {item['status_code']} ({item['cost_ms']}ms)")

    status, dstats = call(base, "GET", "/api/system/data/stats", token=token)
    check("数据量统计", status == 200 and dstats.get("operation_record", 0) > 0, str(dstats)[:200])
    if status == 200:
        print(f"        数据量：{dstats}")

    # 权限校验
    section("权限校验")
    status, viewer_data = call(base, "POST", "/api/auth/login", body={"username": "viewer", "password": "view123"})
    if check("只读用户登录", status == 200 and "access_token" in viewer_data, str(viewer_data)[:150]):
        viewer_token = viewer_data["access_token"]

        status, denied = call(base, "GET", "/api/system/users", token=viewer_token)
        check("只读用户访问用户管理被拒绝", status == 403, f"status={status}")

        status, readable = call(base, "GET", "/api/vehicle/", token=viewer_token,
                                params={"page": 1, "page_size": 1})
        check("只读用户可以查看业务数据", status == 200, f"status={status}")

        status, denied_write = call(
            base, "POST", "/api/region/", token=viewer_token,
            body={"code": "VIEWER1", "name": "只读用户不该建的区域", "region_type": "居民区",
                  "demand_level": 3, "status": 1},
        )
        check("只读用户新增数据被拒绝", status == 403, f"status={status} {str(denied_write)[:150]}")

        status, denied_del = call(base, "DELETE", "/api/operation/1", token=viewer_token)
        check("只读用户删除数据被拒绝", status == 403, f"status={status}")

        status, denied_cfg = call(base, "PUT", "/api/system/configs/DISPATCH_MIN_GAP",
                                  token=viewer_token, body={"config_value": "5"})
        check("只读用户修改配置被拒绝", status == 403, f"status={status}")

        status, own_pwd = call(base, "POST", "/api/auth/change-password", token=viewer_token,
                               body={"old_password": "wrong-old", "new_password": "whatever"})
        check("只读用户仍可调用改密接口（业务校验生效）", status == 400, f"status={status}")

    status, disp_data = call(base, "POST", "/api/auth/login",
                             body={"username": "dispatcher", "password": "disp123"})
    if check("调度员登录", status == 200 and "access_token" in disp_data, str(disp_data)[:150]):
        disp_token = disp_data["access_token"]
        code = f"D{int(time.time()) % 100000}"
        status, created = call(
            base, "POST", "/api/region/", token=disp_token,
            body={"code": code, "name": "调度员创建的测试区域", "region_type": "居民区",
                  "demand_level": 3, "status": 1},
        )
        ok = check("调度员可以执行写操作", status == 200, f"status={status} {str(created)[:150]}")
        if ok:
            call(base, "DELETE", f"/api/region/{created['id']}", token=token)

        status, denied_users = call(base, "GET", "/api/system/users", token=disp_token)
        check("调度员访问用户管理被拒绝", status == 403, f"status={status}")

    # ---------------------------------------------------------------- 汇总
    print("\n" + "=" * 62)
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        print("失败明细：")
        for name, detail in FAILED:
            print(f"  - {name}: {detail}")
        return 1
    print("全部接口测试通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
