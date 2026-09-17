import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.analysis.loaders import LoadError
from app.analysis.pipeline import prepare, stream_analysis
from app.config import settings
from app.schemas import LimitsResponse, PreviewResponse

log = logging.getLogger(__name__)

router = APIRouter(prefix="/analyses", tags=["analyses"])

GOAL_MAX_LENGTH = 500


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / 1_000_000
        raise HTTPException(413, f"File is too large. The limit is {limit_mb:.1f} MB.")
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    return file.filename or "upload.csv", data


@router.get("/limits", response_model=LimitsResponse)
async def limits() -> LimitsResponse:
    return LimitsResponse(
        max_upload_bytes=settings.max_upload_bytes,
        max_rows=settings.max_rows,
        worker_model=settings.worker_model,
        interpreter_model=settings.interpreter_model,
    )


@router.post("/preview", response_model=PreviewResponse)
async def preview(file: Annotated[UploadFile, File()]) -> PreviewResponse:
    filename, data = await _read_upload(file)
    try:
        _, brief = prepare(filename, data)
    except LoadError as exc:
        raise HTTPException(422, str(exc)) from exc
    return PreviewResponse(brief=brief, max_upload_bytes=settings.max_upload_bytes)


@router.post("")
async def analyse(
    file: Annotated[UploadFile, File()],
    goal: Annotated[str | None, Form(max_length=GOAL_MAX_LENGTH)] = None,
) -> StreamingResponse:
    """Run the whole team and stream progress as server-sent events."""
    filename, data = await _read_upload(file)
    if not settings.openai_api_key:
        raise HTTPException(503, "OPENAI_API_KEY is not configured on the server.")
    try:
        df, brief = prepare(filename, data)
    except LoadError as exc:
        raise HTTPException(422, str(exc)) from exc

    goal = (goal or "").strip() or None

    async def events() -> AsyncIterator[str]:
        try:
            async for event in stream_analysis(df, brief, goal):
                yield _sse(event)
        except Exception as exc:  # keep the stream well-formed on unexpected failure
            log.exception("analysis stream failed")
            yield _sse({"event": "error", "message": str(exc) or type(exc).__name__})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: dict[str, Any]) -> str:
    name = event.get("event", "message")
    payload = json.dumps(_jsonable(event), separators=(",", ":"))
    return f"event: {name}\ndata: {payload}\n\n"


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value
