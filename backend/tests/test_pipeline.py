"""Runs the whole graph with the model calls stubbed out."""

import pandas as pd
import pytest

from app.analysis import graph as graph_module
from app.analysis.pipeline import prepare, stream_analysis
from app.analysis.schemas import (
    AnomalyReport,
    DataQualityReport,
    EDAReport,
    InterpretationReport,
    StatisticsReport,
    VisualizationReport,
)

CANNED = {
    "quality": DataQualityReport(score=70, summary="ok", issues=[], cleaning_steps=[]),
    "eda": EDAReport(summary="ok", findings=[]),
    "statistics": StatisticsReport(summary="ok", tests=[]),
    "anomaly": AnomalyReport(summary="ok", total_flagged=0, groups=[]),
    "visualization": VisualizationReport(summary="ok", charts=[]),
    "interpretation": InterpretationReport(
        executive_summary="ok",
        key_insights=[],
        recommendations=[],
        open_questions=[],
        limitations=[],
    ),
}


def _stub(name: str, fail: bool = False):
    async def run(*args, **kwargs):
        if fail:
            raise RuntimeError(f"{name} exploded")
        return CANNED[name]

    return run


@pytest.fixture
def stubbed_agents(monkeypatch):
    def apply(failing: set[str] = frozenset()):
        for name in CANNED:
            module = getattr(graph_module, name)
            monkeypatch.setattr(module, "run", _stub(name, fail=name in failing))

    return apply


async def _collect(df: pd.DataFrame, brief):
    return [event async for event in stream_analysis(df, brief, goal="why")]


def test_prepare_returns_typed_frame_and_brief(sales_csv):
    df, brief = prepare("sales.csv", sales_csv)
    assert pd.api.types.is_datetime64_any_dtype(df["order_date"])
    assert brief.n_rows == len(df)


async def test_stream_emits_every_agent_in_order(sales_csv, stubbed_agents):
    stubbed_agents()
    df, brief = prepare("sales.csv", sales_csv)
    events = await _collect(df, brief)

    assert events[0]["event"] == "brief"
    assert events[-1]["event"] == "done"
    finished = [e["agent"] for e in events if e["event"] == "agent_finished"]
    assert finished[0] == "data_quality"
    assert set(finished[1:4]) == {"eda", "statistics", "anomaly"}
    assert finished[4:] == ["visualization", "interpretation"]
    reports = events[-1]["reports"]
    assert reports["interpretation"].executive_summary == "ok"
    assert events[-1]["errors"] == []


async def test_failed_agent_is_reported_and_run_continues(sales_csv, stubbed_agents):
    stubbed_agents(failing={"statistics"})
    df, brief = prepare("sales.csv", sales_csv)
    events = await _collect(df, brief)

    failed = [e for e in events if e["event"] == "agent_failed"]
    assert [e["agent"] for e in failed] == ["statistics"]
    assert "exploded" in failed[0]["message"]
    done = events[-1]
    assert done["reports"]["stats"] is None
    assert done["reports"]["interpretation"] is not None
    assert [e.agent for e in done["errors"]] == ["statistics"]
