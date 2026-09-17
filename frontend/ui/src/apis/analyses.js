import axios from "axios";

import { BASE_URL } from "apis/constants";
import { parseSseChunks } from "utils/sse";

const fetchLimits = () =>
  axios.get("/analyses/limits").then((response) => response.data);

const preview = (file) => {
  const formData = new FormData();
  formData.append("file", file);

  return axios
    .post("/analyses/preview", formData)
    .then((response) => response.data);
};

const readErrorDetail = async (response) => {
  try {
    const data = await response.json();
    return data?.detail || `Request failed with status ${response.status}`;
  } catch {
    return `Request failed with status ${response.status}`;
  }
};

// Streams a run over SSE. `onEvent` is called with { event, data } for every
// frame as it arrives (event names: brief, agent_started, agent_finished,
// agent_failed, done, error). Errors that happen before the stream starts
// (413/422/503) are thrown as a plain Error with the server's `detail`.
const streamAnalysis = async ({ file, goal, onEvent, signal }) => {
  const formData = new FormData();
  formData.append("file", file);
  if (goal) {
    formData.append("goal", goal);
  }

  const response = await fetch(`${BASE_URL}/analyses`, {
    method: "POST",
    body: formData,
    signal,
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const { events, remainder } = parseSseChunks(buffer);
    buffer = remainder;
    events.forEach(onEvent);
  }
};

export { fetchLimits, preview, streamAnalysis };
