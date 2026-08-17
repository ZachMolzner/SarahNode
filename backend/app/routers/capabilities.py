from fastapi import APIRouter

from app.agent.runtime import agent_runtime

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("")
async def get_capabilities() -> dict[str, object]:
    return agent_runtime.capabilities()
