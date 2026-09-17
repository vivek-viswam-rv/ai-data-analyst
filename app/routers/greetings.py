from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas import MessageResponse

router = APIRouter(prefix="/greetings", tags=["greetings"])


@router.get("", response_model=MessageResponse)
async def get_greeting(
    name: Annotated[str, Query(min_length=1, max_length=50)] = "world",
) -> MessageResponse:
    return MessageResponse(message=f"Hello, {name}!")
