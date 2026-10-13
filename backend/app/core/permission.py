"""只读角色（viewer）写操作拦截中间件。

设计说明
--------
系统共有三种角色：

* ``admin``    系统管理员 —— 全部权限
* ``operator`` 调度员     —— 业务数据的读写、预测与调度
* ``viewer``   只读用户   —— 只能查看，不能产生任何数据变更

权限校验采用**集中式中间件**而不是逐个接口加依赖，原因有两个：

1. 不会因为新增接口忘记加依赖而出现权限漏洞（fail-safe）；
2. 与「操作日志中间件」共用同一套令牌解析逻辑，职责清晰。

注意：登录、退出、修改本人密码这三类接口即使对只读用户也必须放行，
否则只读账号无法登录或修改自己的密码。
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .security import decode_token_claims

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

#: 只读用户也允许调用的写接口（前缀匹配）
ALLOWED_FOR_VIEWER = (
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/change-password",
)


class ReadOnlyGuardMiddleware(BaseHTTPMiddleware):
    """拦截只读用户发起的写操作。"""

    async def dispatch(self, request, call_next):
        method = request.method.upper()
        path = request.url.path
        if method not in WRITE_METHODS or not path.startswith("/api"):
            return await call_next(request)
        if path.startswith(ALLOWED_FOR_VIEWER):
            return await call_next(request)

        claims = decode_token_claims(self._token(request), verify_exp=False)
        if claims and claims.get("role") == "viewer":
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "当前账号为只读用户（viewer），只能查看数据，不能执行新增/修改/删除操作"
                },
            )
        return await call_next(request)

    @staticmethod
    def _token(request) -> str:
        header = request.headers.get("authorization") or ""
        if header.lower().startswith("bearer "):
            return header[7:].strip()
        return ""
