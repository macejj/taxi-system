"""运营数据分析接口。"""
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..core.deps import get_current_user
from ..core.sqlutil import date_range
from ..database import get_db
from ..services import analytics

router = APIRouter()


@router.get("/overview", summary="运营 KPI 总览（含环比）")
def overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.kpi_overview(db, start, end)


@router.get("/income-trend", summary="收入趋势（日/周/月）")
def income_trend(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    group_by: str = Query("day", pattern="^(hour|day|week|month)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.income_trend(db, start, end, group_by)


@router.get("/hourly-profile", summary="24 小时需求—供给分布")
def hourly_profile(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.hourly_profile(db, start, end)


@router.get("/weekday-profile", summary="周一至周日分布")
def weekday_profile(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=56)
    return analytics.weekday_profile(db, start, end)


@router.get("/heatmap", summary="星期 × 小时需求热力图")
def heatmap(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=28)
    return analytics.heatmap(db, start, end)


@router.get("/region-ranking", summary="区域热度排行")
def region_ranking(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.region_ranking(db, start, end)


@router.get("/region-compare", summary="区域多指标对比（雷达图）")
def region_compare(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    region_ids: Optional[str] = Query(None, description="逗号分隔的区域 ID"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    ids = [int(x) for x in region_ids.split(",") if x.strip().isdigit()] if region_ids else None
    return analytics.region_compare(db, start, end, ids)


@router.get("/load-rate", summary="里程利用率（载客率/空驶率）")
def load_rate(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    region_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.load_rate(db, start, end, vehicle_id, region_id)


@router.get("/driver-ranking", summary="驾驶员绩效排行")
def driver_ranking(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_n: int = Query(10, ge=1, le=200),
    sort_by: str = Query("income", pattern="^(income|order_count|score|rating)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.driver_ranking(db, start, end, top_n, sort_by)


@router.get("/vehicle-efficiency", summary="车辆运营效率排行")
def vehicle_efficiency(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_n: int = Query(10, ge=1, le=200),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.vehicle_efficiency(db, start, end, top_n, order)


@router.get("/pay-type", summary="支付方式占比")
def pay_type(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.pay_type_distribution(db, start, end)


@router.get("/weather-impact", summary="天气影响分析")
def weather_impact(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return analytics.weather_impact(db, start, end)


@router.get("/abnormal-alert", summary="运营异常预警")
def abnormal_alert(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return analytics.abnormal_alerts(db, days)


@router.get("/dashboard", summary="运营分析驾驶舱（一次返回多组图表数据）")
def analysis_dashboard(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    start, end = date_range(start_date, end_date, default_days=30)
    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "kpi": analytics.kpi_overview(db, start, end),
        "income_trend": analytics.income_trend(db, start, end, "day"),
        "hourly": analytics.hourly_profile(db, start, end),
        "weekday": analytics.weekday_profile(db, start, end),
        "regions": analytics.region_ranking(db, start, end)[:10],
        "pay_types": analytics.pay_type_distribution(db, start, end),
        "driver_top": analytics.driver_ranking(db, start, end, 10, "score"),
        "vehicle_top": analytics.vehicle_efficiency(db, start, end, 10, "desc"),
    }
