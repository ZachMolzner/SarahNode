import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config.settings import settings
from app.core.container import stream_orchestrator
from app.core.logging import setup_logging
from app.routers.control import router as control_router
from app.routers.health import router as health_router

setup_logging()

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(control_router)


@app.on_event("startup")
async def on_startup() -> None:
    await stream_orchestrator.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await stream_orchestrator.stop()


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
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
