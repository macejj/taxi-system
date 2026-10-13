"""操作日志中间件：记录写操作，便于审计与问题追踪。"""
import time

from starlette.middleware.base import BaseHTTPMiddleware

from ..database import SessionLocal
from .. import models
from .security import decode_token_claims

MODULE_MAP = (
    ("/api/auth", "认证"),
    ("/api/region", "区域管理"),
    ("/api/vehicle", "车辆管理"),
    ("/api/driver", "驾驶员管理"),
    ("/api/assignment", "人车绑定"),
    ("/api/operation", "运营数据"),
    ("/api/demand", "需求数据"),
    ("/api/analysis", "运营分析"),
    ("/api/forecast", "需求预测"),
    ("/api/dispatch", "调度决策"),
    ("/api/dashboard", "驾驶舱"),
    ("/api/system", "系统管理"),
)

ACTION_TEXT = {"POST": "新增", "PUT": "修改", "PATCH": "修改", "DELETE": "删除"}

#: 这些路径属于高频只读或自身已记录日志，跳过
SKIP_PREFIX = ("/api/system/logs",)


def _module_of(path: str) -> str:
    for prefix, name in MODULE_MAP:
        if path.startswith(prefix):
            return name
    return "其他"


class OperationLogMiddleware(BaseHTTPMiddleware):
    """把 POST / PUT / DELETE 请求写入 operation_log 表。"""

    async def dispatch(self, request, call_next):
        method = request.method.upper()
        path = request.url.path
        if method not in ACTION_TEXT or not path.startswith("/api"):
            return await call_next(request)
        if path.startswith(SKIP_PREFIX):
            return await call_next(request)

        started = time.time()
        response = await call_next(request)
        cost_ms = int((time.time() - started) * 1000)

        try:
            username = self._username(request)
            db = SessionLocal()
            try:
                db.add(
                    models.OperationLog(
                        username=username,
                        module=_module_of(path),
                        operation=f"{ACTION_TEXT[method]}{_module_of(path)}数据",
                        method=method,
                        path=path[:200],
                        ip=request.client.host if request.client else None,
                        status_code=response.status_code,
                        cost_ms=cost_ms,
                    )
                )
                db.commit()
            finally:
                db.close()
        except Exception:  # pragma: no cover - 日志失败不应影响主流程
            pass
        return response

    @staticmethod
    def _username(request) -> str | None:
        """从 Authorization 头里解析用户名（不校验有效期，仅用于记录）。"""
        header = request.headers.get("authorization") or ""
        if not header.lower().startswith("bearer "):
            return None
        claims = decode_token_claims(header[7:].strip(), verify_exp=False)
        return claims.get("sub") if claims else None
