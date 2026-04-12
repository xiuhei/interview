from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import ok
from app.db.session import get_db
from app.services.growth_service import GrowthService


router = APIRouter()


@router.get("/insight")
def insight(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(GrowthService(db).get_growth_insight(user.id))


@router.get("/trends")
def trends(user=Depends(get_current_user), db: Session = Depends(get_db)):
    insight = GrowthService(db).get_growth_insight(user.id)
    return ok(insight.trends)


@router.get("/weaknesses")
def weaknesses(user=Depends(get_current_user), db: Session = Depends(get_db)):
    insight = GrowthService(db).get_growth_insight(user.id)
    return ok(insight.weaknesses)


@router.get("/plan")
def plan(user=Depends(get_current_user), db: Session = Depends(get_db)):
    insight = GrowthService(db).get_growth_insight(user.id)
    return ok(insight.plan)
