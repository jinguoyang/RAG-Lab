from fastapi import APIRouter
from app.api.routes.bindings import router as bindings_router
from app.api.routes.classroom import router as classroom_router
from app.api.routes.health import router as health_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.training_plans import router as training_plans_router
from app.api.routes.training_questions import router as training_questions_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(bindings_router)
api_router.include_router(classroom_router)
api_router.include_router(reviews_router)
api_router.include_router(training_plans_router)
api_router.include_router(training_questions_router)
