from app.database import SessionLocal, engine, Base
from app import models
from app.utils.security import get_password_hash

# 创建所有表（如果尚未创建）
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# 检查是否已存在管理员
existing = db.query(models.User).filter(models.User.username == "admin").first()
if existing:
    print("管理员已存在，跳过创建")
else:
    admin = models.User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        real_name="管理员",
        role="admin"
    )
    db.add(admin)
    db.commit()
    print("管理员创建成功")

db.close()