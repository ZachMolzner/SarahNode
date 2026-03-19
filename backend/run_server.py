import uvicorn

from app.config.settings import resolve_backend_host, settings


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=resolve_backend_host(),
        port=settings.backend_port,
        reload=settings.env == "dev",
    )
