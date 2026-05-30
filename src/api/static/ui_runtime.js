export function isAtBottom(panel) {
  return panel.scrollHeight - panel.scrollTop - panel.clientHeight < 12;
}

export function scrollToBottom(panel) {
  panel.scrollTop = panel.scrollHeight;
}

export function progressHint(state) {
  if (state.status !== "running") return "等待任务提交";
  const staleSec = (Date.now() - state.lastProgressAt) / 1000;
  if (staleSec > 5) return "求解中，等待下一批进度事件...";
  return "实时流连接正常，持续接收进度";
}

export function shownProgress(state) {
  return Math.max(state.pct, Math.floor(state.visualPct));
}

export function advanceVisualProgress(state) {
  if (state.status !== "running") return;
  const cap = Math.min(95, Math.max(state.targetPct, phaseCap(state.phase)));
  if (state.visualPct < cap) state.visualPct = Math.min(cap, state.visualPct + 0.4);
}

export function nudgeProgressByLog(state) {
  if (state.status !== "running") return;
  const cap = Math.min(95, Math.max(state.targetPct, phaseCap(state.phase)));
  if (state.visualPct < cap) state.visualPct = Math.min(cap, state.visualPct + 0.25);
}

export function flushLogs(nodes, state) {
  const frag = document.createDocumentFragment();
  while (state.logQueue.length) {
    const entry = state.logQueue.shift();
    const line = document.createElement("div");
    line.className = entry.cls || "";
    line.textContent = entry.text;
    frag.appendChild(line);
  }
  nodes.logPanel.appendChild(frag);
  nodes.logCount.textContent = `${nodes.logPanel.childElementCount} lines`;
  if (state.autoFollow) scrollToBottom(nodes.logPanel);
  state.flushPending = false;
}

function phaseCap(phase) {
  return ({
    load: 12,
    candidates: 28,
    build: 52,
    solve: 92,
    output: 99,
    done: 100,
  })[phase] ?? 8;
}
