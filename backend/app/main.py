from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app import models
from app.routers import auth, vehicle, driver, operation, analysis, user

Base.metadata.create_all(bind=engine)

app = FastAPI(title="出租车运营管理与数据分析系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(vehicle.router, prefix="/api/vehicle", tags=["车辆"])
app.include_router(driver.router, prefix="/api/driver", tags=["驾驶员"])
app.include_router(operation.router, prefix="/api/operation", tags=["运营数据"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["数据分析"])
app.include_router(user.router, prefix="/api/user", tags=["用户管理"])