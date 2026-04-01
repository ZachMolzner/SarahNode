import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import resolve_cors_origins, resolve_ws_allowed_origins, settings
from app.core.container import stream_orchestrator
from app.core.logging import setup_logging
from app.routers.control import router as control_router
from app.routers.health import router as health_router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
cors_origins = resolve_cors_origins()
cors_allow_credentials = settings.cors_allow_credentials and "*" not in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_allow_credentials,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router)
app.include_router(control_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled backend error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


@app.on_event("startup")
async def on_startup() -> None:
    await stream_orchestrator.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await stream_orchestrator.stop()


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    allowed_origins = resolve_ws_allowed_origins()
    origin = websocket.headers.get("origin")
    if origin and origin not in allowed_origins:
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    await stream_orchestrator.register_ws(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        await stream_orchestrator.unregister_ws(websocket)
