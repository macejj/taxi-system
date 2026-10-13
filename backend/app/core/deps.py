"""公共依赖：身份认证、角色校验、分页。"""
from typing import Any, Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Query as OrmQuery
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from .security import ALGORITHM, SECRET_KEY

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login", auto_error=False
)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="登录状态无效或已过期，请重新登录",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    """解析 Bearer 令牌并返回当前登录用户。"""
    if not token:
        raise CREDENTIALS_ERROR
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise CREDENTIALS_ERROR
    except JWTError:
        raise CREDENTIALS_ERROR

    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise CREDENTIALS_ERROR
    if user.status != 1:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    return user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """管理员权限校验。"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限执行该操作（需要管理员）")
    return current_user


class PageParams:
    """统一分页参数。"""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(20, ge=1, le=500, description="每页条数"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size
        self.limit = page_size


def paginate(query: OrmQuery, params: PageParams) -> dict[str, Any]:
    """对查询做分页，返回统一结构。"""
    total = query.order_by(None).count()
    items = query.offset(params.offset).limit(params.limit).all()
    return {
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "items": items,
    }
