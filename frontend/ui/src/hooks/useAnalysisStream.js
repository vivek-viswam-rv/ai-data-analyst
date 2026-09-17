import { useCallback, useEffect, useReducer, useRef } from "react";

import { streamAnalysis } from "apis/analyses";
import {
  AGENT_ORDER,
  AGENT_REPORT_KEY,
  ANALYSIS_STORAGE_KEY,
} from "constants/analysis";

const buildAgentMap = (agents, value) =>
  agents.reduce((acc, agent) => ({ ...acc, [agent]: value }), {});

const initialState = {
  status: "idle", // idle | running | done | error
  restored: false,
  agents: AGENT_ORDER,
  agentStatus: buildAgentMap(AGENT_ORDER, "waiting"),
  reports: {},
  agentMessages: {},
  runErrors: [],
  runError: null,
  brief: null,
  filename: null,
  goal: null,
  startedAt: null,
  elapsedMs: 0,
};

const reducer = (state, action) => {
  switch (action.type) {
    case "START":
      return {
        ...initialState,
        status: "running",
        restored: false,
        filename: action.filename,
        goal: action.goal,
        startedAt: action.startedAt,
      };
    case "BRIEF":
      return {
        ...state,
        brief: action.brief,
        agents: action.agents,
        agentStatus: buildAgentMap(action.agents, "waiting"),
      };
    case "AGENT_STARTED":
      return {
        ...state,
        agentStatus: { ...state.agentStatus, [action.agent]: "running" },
      };
    case "AGENT_FINISHED":
      return {
        ...state,
        agentStatus: { ...state.agentStatus, [action.agent]: "done" },
        reports: { ...state.reports, [action.agent]: action.report },
      };
    case "AGENT_FAILED":
      return {
        ...state,
        agentStatus: { ...state.agentStatus, [action.agent]: "failed" },
        agentMessages: {
          ...state.agentMessages,
          [action.agent]: action.message,
        },
      };
    case "DONE": {
      const reports = { ...state.reports };
      const agentMessages = { ...state.agentMessages };
      state.agents.forEach((agent) => {
        const reportKey = AGENT_REPORT_KEY[agent];
        if (
          reports[agent] === undefined &&
          action.reports?.[reportKey] != null
        ) {
          reports[agent] = action.reports[reportKey];
        }
      });
      (action.errors || []).forEach(({ agent, message }) => {
        if (!agentMessages[agent]) {
          agentMessages[agent] = message;
        }
      });
      return {
        ...state,
        status: "done",
        reports,
        agentMessages,
        runErrors: action.errors || [],
      };
    }
    case "RUN_ERROR":
      return {
        ...state,
        status: "error",
        runError: action.message,
      };
    case "TICK":
      return { ...state, elapsedMs: action.elapsedMs };
    case "HYDRATE":
      return {
        ...action.snapshot,
        restored: true,
      };
    default:
      return state;
  }
};

const loadPersistedRun = () => {
  try {
    const raw = sessionStorage.getItem(ANALYSIS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const persistRun = (state) => {
  try {
    const snapshot = {
      status: state.status,
      restored: true,
      agents: state.agents,
      agentStatus: state.agentStatus,
      reports: state.reports,
      agentMessages: state.agentMessages,
      runErrors: state.runErrors,
      runError: state.runError,
      brief: state.brief,
      filename: state.filename,
      goal: state.goal,
      startedAt: state.startedAt,
      elapsedMs: state.elapsedMs,
    };
    sessionStorage.setItem(ANALYSIS_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    // sessionStorage can throw (private mode, quota); persistence is best-effort.
  }
};

// Drives one analysis run over SSE, exposing per-agent status/reports plus
// elapsed time, and persists finished runs to sessionStorage so a refresh on
// /analysis can still show results.
const useAnalysisStream = () => {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef(null);

  const start = useCallback((file, goal) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const startedAt = Date.now();
    dispatch({
      type: "START",
      filename: file.name,
      goal: goal || null,
      startedAt,
    });

    streamAnalysis({
      file,
      goal,
      signal: controller.signal,
      onEvent: ({ event, data }) => {
        switch (event) {
          case "brief":
            dispatch({ type: "BRIEF", brief: data.brief, agents: data.agents });
            break;
          case "agent_started":
            dispatch({ type: "AGENT_STARTED", agent: data.agent });
            break;
          case "agent_finished":
            dispatch({
              type: "AGENT_FINISHED",
              agent: data.agent,
              report: data.report,
            });
            break;
          case "agent_failed":
            dispatch({
              type: "AGENT_FAILED",
              agent: data.agent,
              message: data.message,
            });
            break;
          case "done":
            dispatch({
              type: "DONE",
              reports: data.reports,
              errors: data.errors,
            });
            break;
          case "error":
            dispatch({ type: "RUN_ERROR", message: data.message });
            break;
          default:
            break;
        }
      },
    }).catch((error) => {
      if (error.name === "AbortError") {
        return;
      }
      dispatch({ type: "RUN_ERROR", message: error.message });
    });
  }, []);

  const hydrate = useCallback(() => {
    const snapshot = loadPersistedRun();
    if (snapshot) {
      dispatch({ type: "HYDRATE", snapshot });
    }
    return Boolean(snapshot);
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    if (state.status !== "running" || !state.startedAt) {
      return undefined;
    }
    const id = setInterval(() => {
      dispatch({ type: "TICK", elapsedMs: Date.now() - state.startedAt });
    }, 1000);
    return () => clearInterval(id);
  }, [state.status, state.startedAt]);

  useEffect(() => {
    if (state.status === "done" || state.status === "error") {
      persistRun(state);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.status]);

  return { state, start, hydrate };
};

export default useAnalysisStream;
