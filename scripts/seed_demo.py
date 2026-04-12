import json
from pathlib import Path
import sys
import time

from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.core.security import get_password_hash  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import CompetencyDimension, JobPosition, User  # noqa: E402
from app.models.enums import UserRole  # noqa: E402


POSITION_SEEDS = [
    {
        "code": "cpp_backend",
        "name": "C++后端开发",
        "description": "面向高并发、系统设计和项目真实性的后端岗位。",
        "weight_config": {
            "cpp_language": 0.22,
            "os_network": 0.18,
            "algorithm": 0.15,
            "system_design": 0.2,
            "performance": 0.15,
            "project_depth": 0.1,
        },
        "competencies": [
            ("cpp_language", "C++基础与语言特性", "RAII、智能指针、模板、STL", 0.22),
            ("os_network", "操作系统与网络", "进程线程、锁、IO模型、TCP/HTTP", 0.18),
            ("algorithm", "数据结构与算法", "复杂度分析与常用结构", 0.15),
            ("system_design", "后端系统设计", "缓存、数据库、消息队列、分布式基础", 0.20),
            ("performance", "性能优化与排障", "瓶颈定位、压测、故障排查", 0.15),
            ("project_depth", "项目真实性与深度", "职责、指标、方案、复盘", 0.10),
        ],
    },
    {
        "code": "web_frontend",
        "name": "Web前端开发",
        "description": "面向浏览器原理、Vue 工程化和前端架构的岗位。",
        "weight_config": {
            "frontend_foundation": 0.18,
            "vue_engineering": 0.18,
            "browser_principle": 0.16,
            "network_performance": 0.16,
            "architecture": 0.18,
            "project_depth": 0.14,
        },
        "competencies": [
            ("frontend_foundation", "前端基础", "HTML/CSS/JavaScript/TypeScript", 0.18),
            ("vue_engineering", "Vue工程化能力", "组件拆分、构建、路由、权限", 0.18),
            ("browser_principle", "浏览器原理", "渲染流程、事件循环、缓存", 0.16),
            ("network_performance", "网络与性能优化", "首屏、缓存、包体积、监控", 0.16),
            ("architecture", "前端架构设计", "状态流、公共能力、模块边界", 0.18),
            ("project_depth", "项目真实性与深度", "个人贡献、收益、复盘", 0.14),
        ],
    },
]

SEED_RETRY_ATTEMPTS = 10
SEED_RETRY_DELAY_SECONDS = 2


def seed_users(db):
    users_path = ROOT / "data/demo/users/users.json"
    users = json.loads(users_path.read_text(encoding="utf-8-sig"))
    for item in users:
        existing = db.query(User).filter(User.username == item["username"]).first()
        if existing:
            continue
        db.add(
            User(
                email=item["email"],
                username=item["username"],
                full_name=item["full_name"],
                hashed_password=get_password_hash(item["password"]),
                role=UserRole(item["role"]),
            )
        )


def seed_positions(db):
    for item in POSITION_SEEDS:
        position = db.query(JobPosition).filter(JobPosition.code == item["code"]).first()
        if not position:
            position = JobPosition(
                code=item["code"],
                name=item["name"],
                description=item["description"],
                weight_config=item["weight_config"],
                question_count_default=6,
            )
            db.add(position)
            db.flush()
        for code, name, description, weight in item["competencies"]:
            exists = (
                db.query(CompetencyDimension)
                .filter(CompetencyDimension.position_id == position.id, CompetencyDimension.code == code)
                .first()
            )
            if exists:
                continue
            db.add(
                CompetencyDimension(
                    position_id=position.id,
                    code=code,
                    name=name,
                    description=description,
                    weight=weight,
                    is_required=True,
                )
            )


def run_seed() -> None:
    db = SessionLocal()
    try:
        seed_users(db)
        seed_positions(db)
        db.commit()
        print("seeded demo data")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    last_exc: OperationalError | None = None
    for attempt in range(1, SEED_RETRY_ATTEMPTS + 1):
        try:
            run_seed()
            last_exc = None
            break
        except OperationalError as exc:
            last_exc = exc
            if attempt == SEED_RETRY_ATTEMPTS:
                break
            print(f"seed demo waiting for mysql ({attempt}/{SEED_RETRY_ATTEMPTS}): {exc}")
            time.sleep(SEED_RETRY_DELAY_SECONDS)
    if last_exc is not None:
        raise last_exc
