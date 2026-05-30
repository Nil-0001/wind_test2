export function inferLogClass(line) {
  if (/error|traceback|failed|memoryerror/i.test(line)) return "err";
  if (/optimal|done in|solver done|cad exported/i.test(line)) return "ok";
  if (/warn|maxTimeLimit|presolve|cuts/i.test(line)) return "warn";
  if (/solving|loading|generated|model|mip/i.test(line)) return "info";
  return "";
}

function parseSSEBlock(block) {
  const event = { event: "message", data: "" };
  const dataLines = [];
  for (const line of block.split("\n")) {
    const idx = line.indexOf(":");
    if (idx < 0) continue;
    const key = line.slice(0, idx).trim();
    const value = line.slice(idx + 1).trim();
    if (key === "event") event.event = value;
    if (key === "data") dataLines.push(value);
  }
  event.data = dataLines.join("\n");
  try {
    event.data = JSON.parse(event.data);
  } catch {
    // keep raw text when data is not JSON.
  }
  return event;
}

export async function fetchSampleText() {
  const resp = await fetch("/sample");
  if (!resp.ok) throw new Error(`加载样例失败: HTTP ${resp.status}`);
  return await resp.text();
}

export async function streamSolve(body, onEvent, onDebug) {
  const resp = await fetch("/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`求解请求失败: HTTP ${resp.status}`);
  }
  const contentType = (resp.headers.get("content-type") || "").toLowerCase();
  if (!contentType.includes("text/event-stream")) {
    const payload = await resp.json().catch(async () => ({ error: await resp.text() }));
    const msg = payload?.error || payload?.detail || "未知错误";
    throw new Error(`求解失败: ${msg}`);
  }
  if (!resp.body) {
    throw new Error("求解请求失败: 空响应流");
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const debug = (msg) => { if (onDebug) onDebug(`${new Date().toISOString()} ${msg}`); };
  debug("SSE stream opened");
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    debug(`chunk bytes=${value?.byteLength ?? 0}`);
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      if (chunk.startsWith(":")) continue;
      const ev = parseSSEBlock(chunk);
      onEvent(ev);
      debug(`event=${ev.event}`);
    }
  }
  if (buffer.trim() && !buffer.startsWith(":")) {
    const ev = parseSSEBlock(buffer);
    onEvent(ev);
    debug(`tail-event=${ev.event}`);
  }
  debug("SSE stream closed");
}

export async function downloadCad(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`CAD下载失败: HTTP ${resp.status}`);
  const blob = await resp.blob();
  const cd = resp.headers.get("content-disposition") || "";
  const match = cd.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] || "stowage_latest.dxf";
  const link = document.createElement("a");
  const blobUrl = URL.createObjectURL(blob);
  link.href = blobUrl;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1200);
}
