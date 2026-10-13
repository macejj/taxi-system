"""认证与个人信息相关接口。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..core.deps import get_current_user
from ..core.security import create_access_token, get_password_hash, verify_password
from ..database import get_db

router = APIRouter()


@router.post("/login", response_model=schemas.Token, summary="用户登录")
def login(user_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == user_data.username).first()
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    if user.status == 0:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    token = create_access_token({"sub": user.username, "role": user.role})
    user.last_login = datetime.now()
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.get("/me", response_model=schemas.UserOut, summary="获取当前登录用户")
def read_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", response_model=schemas.Message, summary="修改自己的密码")
def change_password(
    payload: schemas.PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not verify_password(payload.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    current_user.password_hash = get_password_hash(payload.new_password)
    db.commit()
    return {"message": "密码修改成功，请重新登录"}


@router.post("/logout", response_model=schemas.Message, summary="退出登录")
def logout(current_user: models.User = Depends(get_current_user)):
    # JWT 为无状态令牌，前端清除本地令牌即可
    return {"message": "已退出登录"}
