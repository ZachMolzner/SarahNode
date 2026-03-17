from fastapi import APIRouter

from app.config.settings import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.env,
        "port": settings.backend_port,
    }
