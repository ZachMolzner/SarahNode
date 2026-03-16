from datetime import datetime

from pydantic import BaseModel, Field


class SystemEvent(BaseModel):
    type: str
    payload: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)
