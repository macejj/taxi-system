"""数据库初始化脚本：建表 → 初始化管理员 → 补齐系统配置。

用法：
    python scripts/init_db.py            # 建表并初始化管理员
    python scripts/init_db.py --reset    # 先删除所有表再重建（会丢数据！）
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models  # noqa: F401,E402
from app.config import settings  # noqa: E402
from app.core.config_store import ensure_defaults  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402

DEFAULT_USERS = (
    ("admin", "admin123", "系统管理员", "admin"),
    ("dispatcher", "disp123", "调度员", "operator"),
    ("viewer", "view123", "只读用户", "viewer"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化出租车运营管理系统数据库")
    parser.add_argument("--reset", action="store_true", help="先删除所有表再重建（危险）")
    args = parser.parse_args()

    print(f"数据库：{settings.DATABASE_URL.split('@')[-1]}")
    if args.reset:
        confirm = input("确认要删除所有表并重建吗？数据将全部丢失 (yes/no): ")
        if confirm.strip().lower() != "yes":
            print("已取消")
            return
        Base.metadata.drop_all(bind=engine)
        print("已删除所有表")

    Base.metadata.create_all(bind=engine)
    print(f"建表完成，共 {len(Base.metadata.tables)} 张表：")
    for name in Base.metadata.tables:
        print(f"  - {name}")

    db = SessionLocal()
    try:
        created = ensure_defaults(db)
        print(f"系统参数：新增 {created} 项")

        for username, password, real_name, role in DEFAULT_USERS:
            exists = db.query(models.User).filter(models.User.username == username).first()
            if exists:
                print(f"用户 {username} 已存在，跳过")
                continue
            db.add(
                models.User(
                    username=username,
                    password_hash=get_password_hash(password),
                    real_name=real_name,
                    role=role,
                )
            )
            db.commit()
            print(f"创建用户 {username} / {password}（{role}）")
    finally:
        db.close()
    print("初始化完成。接下来可执行：python scripts/seed_data.py")


if __name__ == "__main__":
    main()
