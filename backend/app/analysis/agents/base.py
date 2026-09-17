"""One place that knows how to run a tool-calling agent to a structured answer."""

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.agents.structured_output import ProviderStrategy
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.config import settings

log = logging.getLogger(__name__)


class AgentFailure(RuntimeError):
    """The agent ran but did not produce a usable report."""


def worker_model() -> ChatOpenAI:
    return _model(settings.worker_model)


def interpreter_model() -> ChatOpenAI:
    return _model(settings.interpreter_model)


def _model(name: str) -> ChatOpenAI:
    # gpt-5.x models only accept function tools through the Responses API.
    return ChatOpenAI(
        model=name,
        api_key=settings.openai_api_key or None,
        use_responses_api=True,
        timeout=90,
        max_retries=2,
    )


async def run_agent[T: BaseModel](
    *,
    name: str,
    model: BaseChatModel,
    system_prompt: str,
    tools: Sequence[Any],
    response_format: type[T],
    user_message: str,
    max_tool_calls: int = 12,
    max_model_calls: int = 16,
    timeout_s: float = 150,
) -> T:
    """Run a ReAct loop with hard caps and return the validated structured answer.

    Caps matter: a small model that keeps calling tools would otherwise eat the
    whole request budget. When the tool cap is hit the model is told so and has
    to answer with what it has.
    """
    agent = create_agent(
        model,
        list(tools),
        system_prompt=system_prompt,
        response_format=ProviderStrategy(response_format, strict=True),
        middleware=[
            ToolCallLimitMiddleware(run_limit=max_tool_calls, exit_behavior="continue"),
            ModelCallLimitMiddleware(run_limit=max_model_calls, exit_behavior="end"),
        ],
        name=name,
    )
    try:
        result = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": [HumanMessage(content=user_message)]},
                config={"recursion_limit": 2 * (max_tool_calls + max_model_calls) + 10},
            ),
            timeout=timeout_s,
        )
    except TimeoutError as exc:
        raise AgentFailure(f"{name} did not finish within {timeout_s:.0f}s") from exc

    structured = result.get("structured_response")
    if structured is None:
        raise AgentFailure(f"{name} stopped without a final report")
    if not isinstance(structured, response_format):
        structured = response_format.model_validate(structured)
    log.info("%s finished with %d messages", name, len(result.get("messages", [])))
    return structured
