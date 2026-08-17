import os
import sys
import uvicorn

from app.agent.windows_display import enable_per_monitor_dpi_awareness
from app.config.settings import resolve_backend_host, settings


if __name__ == "__main__":
    # Set this before uvicorn imports app.main so screenshot and pointer coordinates
    # use the same physical-pixel coordinate system on scaled Windows displays.
    enable_per_monitor_dpi_awareness()

    launched_by_tauri = os.getenv("SARAHNODE_TAURI", "0") == "1"
    print(
        "SarahNode backend startup:",
        {
            "python": sys.executable,
            "cwd": os.getcwd(),
            "llm_provider": settings.llm_provider,
            "openai_key_loaded": bool(settings.openai_api_key),
            "openai_model": settings.openai_model,
            "tauri": launched_by_tauri,
        },
        flush=True,
    )

    uvicorn.run(
        "app.main:app",
        host=resolve_backend_host(),
        port=settings.backend_port,
        reload=(settings.env == "dev" and not launched_by_tauri),
    )
