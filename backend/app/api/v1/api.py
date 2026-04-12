from fastapi import APIRouter

from app.api.v1.endpoints import auth, growth, interviews, knowledge_base, positions, records, resumes, system


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(positions.router, prefix="/positions", tags=["positions"])
api_router.include_router(knowledge_base.router, prefix="/knowledge-base", tags=["knowledge-base"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
api_router.include_router(interviews.router, prefix="/interviews", tags=["interviews"])
api_router.include_router(records.router, prefix="/records", tags=["records"])
api_router.include_router(growth.router, prefix="/growth", tags=["growth"])
api_router.include_router(system.router, prefix="/system", tags=["system"])