from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user
from app.utils.security import get_password_hash

router = APIRouter()

@router.get("/", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限")
    return db.query(models.User).all()

@router.post("/", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权限")
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    db_user = models.User(
        username=user.username,
        password_hash=get_password_hash(user.password),
        real_name=user.real_name,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user