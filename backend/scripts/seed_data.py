"""仿真数据生成脚本。

用法：
    python scripts/seed_data.py                      # 默认：近 60 天、60 台车、80 名驾驶员
    python scripts/seed_data.py --days 90 --vehicles 80
    python scripts/seed_data.py --no-reset           # 追加数据而不清空
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.services.simulator import run_simulation  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="生成出租车运营仿真数据")
    parser.add_argument("--days", type=int, default=60, help="生成最近多少天的运营流水")
    parser.add_argument("--vehicles", type=int, default=60, help="车辆数量")
    parser.add_argument("--drivers", type=int, default=80, help="驾驶员数量")
    parser.add_argument("--seed", type=int, default=20240501, help="随机种子（保证可复现）")
    parser.add_argument("--no-reset", action="store_true", help="保留现有业务数据，仅追加")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = run_simulation(
            db,
            days=args.days,
            vehicles=args.vehicles,
            drivers=args.drivers,
            seed=args.seed,
            reset=not args.no_reset,
            verbose=True,
        )
    finally:
        db.close()

    print("\n===== 数据生成汇总 =====")
    for key, value in result.items():
        print(f"  {key:12s}: {value}")


if __name__ == "__main__":
    main()
