from pydantic import BaseModel

from app.analysis.profiling import DatasetBrief


class PreviewResponse(BaseModel):
    brief: DatasetBrief
    max_upload_bytes: int


class LimitsResponse(BaseModel):
    max_upload_bytes: int
    max_rows: int
    worker_model: str
    interpreter_model: str
