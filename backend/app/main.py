"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401  确保所有模型被注册
from app.config import settings
from app.core.config_store import ensure_defaults, load_overrides
from app.core.logging import OperationLogMiddleware
from app.core.permission import ReadOnlyGuardMiddleware
from app.database import Base, SessionLocal, engine
from app.routers import (
    analysis,
    assignment,
    auth,
    dashboard,
    demand,
    dispatch,
    driver,
    forecast,
    operation,
    region,
    system,
    vehicle,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时建表并载入数据库中的业务参数。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_defaults(db)
        load_overrides(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "出租车运营管理 + 数据分析 + 需求预测 + 调度决策支持系统。\n\n"
        "- **运营管理**：区域、车辆、驾驶员、人车绑定、营运订单与叫车需求\n"
        "- **数据分析**：KPI、收入趋势、时段/区域分布、里程利用率、绩效排行、异常预警\n"
        "- **需求预测**：季节朴素法 / 移动平均 / Holt-Winters / 多元回归 / 组合模型，滚动回测自动选优\n"
        "- **调度决策**：供需缺口测算、贪心与匈牙利最优指派、调度执行与效果评估"
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# add_middleware 采用「后添加者更靠外层」的顺序：
# 先加角色守卫、后加日志中间件，使得只读用户被拒绝的写请求
# 依然会被记录到 operation_log，便于安全审计。
app.add_middleware(ReadOnlyGuardMiddleware)
app.add_middleware(OperationLogMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """统一异常响应，避免把堆栈直接暴露给前端。"""
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误：{exc}"},
    )


prefix = settings.API_PREFIX
app.include_router(auth.router, prefix=f"{prefix}/auth", tags=["认证"])
app.include_router(dashboard.router, prefix=f"{prefix}/dashboard", tags=["驾驶舱"])
app.include_router(region.router, prefix=f"{prefix}/region", tags=["区域管理"])
app.include_router(vehicle.router, prefix=f"{prefix}/vehicle", tags=["车辆管理"])
app.include_router(driver.router, prefix=f"{prefix}/driver", tags=["驾驶员管理"])
app.include_router(assignment.router, prefix=f"{prefix}/assignment", tags=["人车绑定"])
app.include_router(operation.router, prefix=f"{prefix}/operation", tags=["营运订单"])
app.include_router(demand.router, prefix=f"{prefix}/demand", tags=["叫车需求"])
app.include_router(analysis.router, prefix=f"{prefix}/analysis", tags=["运营分析"])
app.include_router(forecast.router, prefix=f"{prefix}/forecast", tags=["需求预测"])
app.include_router(dispatch.router, prefix=f"{prefix}/dispatch", tags=["调度决策"])
app.include_router(system.router, prefix=f"{prefix}/system", tags=["系统管理"])


@app.get("/", tags=["系统"], summary="服务信息")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api_prefix": settings.API_PREFIX,
    }


@app.get(f"{prefix}/health", tags=["系统"], summary="健康检查")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
