"""Shared state the LangGraph pipeline passes between agents."""

import operator
from dataclasses import dataclass
from typing import Annotated, TypedDict

import pandas as pd
from langchain_core.language_models import BaseChatModel

from app.analysis.profiling import DatasetBrief
from app.analysis.schemas import (
    AgentError,
    DataQualityReport,
    EDAReport,
    InterpretationReport,
    VisualizationReport,
)


@dataclass
class AnalysisContext:
    """Things nodes need that do not belong in checkpointable state.

    The DataFrame stays here: it is large, not serialisable, and every node
    reads it through tools rather than through the model.
    """

    df: pd.DataFrame
    worker: BaseChatModel | None = None
    interpreter: BaseChatModel | None = None


class AnalysisState(TypedDict, total=False):
    filename: str
    goal: str | None
    brief: DatasetBrief
    quality: DataQualityReport | None
    eda: EDAReport | None
    charts: VisualizationReport | None
    interpretation: InterpretationReport | None
    errors: Annotated[list[AgentError], operator.add]


AGENT_ORDER = [
    "data_quality",
    "eda",
    "visualization",
    "interpretation",
]

REPORT_KEYS = {
    "data_quality": "quality",
    "eda": "eda",
    "visualization": "charts",
    "interpretation": "interpretation",
}
