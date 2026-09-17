// Parses a buffered SSE (server-sent events) text stream into frames.
//
// The wire format is lines of `event: <name>` and `data: <json>` separated by
// a blank line (`\n\n`). Frames can be split across chunks, so the caller
// keeps accumulating text into a buffer and calls this after every chunk;
// only complete frames (terminated by `\n\n`) are consumed, and the leftover
// (possibly-partial) text is returned as `remainder` to prefix the next call.
const parseSseChunks = (buffer) => {
  const events = [];
  let remainder = buffer;

  while (true) {
    const boundary = remainder.indexOf("\n\n");
    if (boundary === -1) {
      break;
    }

    const rawFrame = remainder.slice(0, boundary);
    remainder = remainder.slice(boundary + 2);

    const frame = parseSseFrame(rawFrame);
    if (frame) {
      events.push(frame);
    }
  }

  return { events, remainder };
};

// Parses a single frame (the text between two `\n\n` boundaries) into
// { event, data }, or returns null for a frame with no data lines (e.g. a
// blank keep-alive frame).
const parseSseFrame = (rawFrame) => {
  let event = "message";
  const dataLines = [];

  rawFrame.split("\n").forEach((line) => {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  });

  if (dataLines.length === 0) {
    return null;
  }

  const raw = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(raw) };
  } catch {
    return null;
  }
};

export { parseSseChunks, parseSseFrame };
