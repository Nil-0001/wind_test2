import { downloadCad, fetchSampleText, inferLogClass, streamSolve } from "./api_client.js";
import { advanceVisualProgress, flushLogs, isAtBottom, nudgeProgressByLog, progressHint, scrollToBottom, shownProgress } from "./ui_runtime.js";
import { openResultPage } from "./viewer_runtime.js";
const DEFAULT_CFG = { solver_name: "appsi_highs", time_limit_s: 180, x_gap: 500, y_gap: 100, layer1_x_phases: 1, layer1_y_phases: 1, layer23_x_phases: 1, layer23_y_phases: 1, layer4_x_phases: 1, layer4_y_phases: 1 };
const state = { status: "idle", phase: "idle", pct: 0, visualPct: 0, targetPct: 0, msg: "等待开始", elapsed: 0, cadUrl: "/download/cad/latest", result: null, lastProgressAt: 0, autoFollow: true, logQueue: [], flushPending: false };
const nodes = {};
init();
function init() {
  cacheDom();
  bindEvents();
  fillDefaults();
  setTheme(localStorage.getItem("ws_dark") === "1");
  updateStatus("idle");
  renderStats();
  setTab("stats"); nodes.rawInput.value = "";
}
function cacheDom() {
  const ids = ["solverName","timeLimit","xGap","yGap","l1x","l1y","l23x","l23y","l4x","l4y","rawInput","sampleStatus","sampleBtn","solveBtn","cadBtn","jsonBtn","open2dBtn","open3dBtn","themeBtn","statusBadge","phaseLabel","elapsedLabel","progressBar","progressMsg","progressHint","followBtn","logPanel","logCount","statsView","viewer2dWrap","viewer3dWrap","frame2d","frame3d","jsonView","toast"];
  ids.forEach((id) => { nodes[id] = document.getElementById(id); });
  nodes.tabs = Array.from(document.querySelectorAll(".tab"));
}
function bindEvents() {
  nodes.themeBtn.addEventListener("click", () => setTheme(!document.body.classList.contains("dark")));
  nodes.sampleBtn.addEventListener("click", () => loadSample());
  nodes.solveBtn.addEventListener("click", () => solve());
  nodes.cadBtn.addEventListener("click", async () => { try { await downloadCad(state.cadUrl); toast("CAD 下载已开始"); } catch (e) { toast(String(e)); } });
  nodes.jsonBtn.addEventListener("click", () => downloadJson());
  nodes.open2dBtn.addEventListener("click", () => openResultPage(state, "2d", emptyFrame));
  nodes.open3dBtn.addEventListener("click", () => openResultPage(state, "3d", emptyFrame));
  nodes.tabs.forEach((btn) => btn.addEventListener("click", () => setTab(btn.dataset.tab)));
  nodes.logPanel.addEventListener("scroll", () => {
    state.autoFollow = isAtBottom(nodes.logPanel);
    nodes.followBtn.classList.toggle("hidden", state.autoFollow);
  });
  nodes.followBtn.addEventListener("click", () => {
    state.autoFollow = true;
    scrollToBottom(nodes.logPanel);
    nodes.followBtn.classList.add("hidden");
  });
  setInterval(() => tickProgress(), 120);
}
function fillDefaults() {
  nodes.solverName.value = DEFAULT_CFG.solver_name;
  nodes.timeLimit.value = DEFAULT_CFG.time_limit_s;
  nodes.xGap.value = DEFAULT_CFG.x_gap;
  nodes.yGap.value = DEFAULT_CFG.y_gap;
  nodes.l1x.value = DEFAULT_CFG.layer1_x_phases;
  nodes.l1y.value = DEFAULT_CFG.layer1_y_phases;
  nodes.l23x.value = DEFAULT_CFG.layer23_x_phases;
  nodes.l23y.value = DEFAULT_CFG.layer23_y_phases;
  nodes.l4x.value = DEFAULT_CFG.layer4_x_phases;
  nodes.l4y.value = DEFAULT_CFG.layer4_y_phases;
}
function cfg() {
  return { solver_name: nodes.solverName.value || "appsi_highs", time_limit_s: Number(nodes.timeLimit.value), x_gap: Number(nodes.xGap.value), y_gap: Number(nodes.yGap.value), layer1_x_phases: Number(nodes.l1x.value), layer1_y_phases: Number(nodes.l1y.value), layer23_x_phases: Number(nodes.l23x.value), layer23_y_phases: Number(nodes.l23y.value), layer4_x_phases: Number(nodes.l4x.value), layer4_y_phases: Number(nodes.l4y.value) };
}
function setTheme(dark) {
  document.body.classList.toggle("dark", dark);
  localStorage.setItem("ws_dark", dark ? "1" : "0");
  nodes.themeBtn.textContent = dark ? "浅色" : "深色";
}
async function loadSample() {
  nodes.sampleStatus.textContent = "样例加载中...";
  try {
    const text = await fetchSampleText();
    nodes.rawInput.value = text;
    nodes.sampleStatus.textContent = `样例加载成功（${text.length} chars）`;
    toast("样例已加载");
  } catch (e) {
    nodes.sampleStatus.textContent = "样例加载失败";
    appendLog(String(e), "err");
  }
}
async function solve() {
  let testData;
  try { testData = JSON.parse(nodes.rawInput.value); } catch (e) { toast(`JSON解析失败: ${e.message}`); return; }
  updateStatus("running");
  state.phase = "load";
  state.pct = 0;
  state.visualPct = 0;
  state.targetPct = 0;
  state.msg = "提交求解请求...";
  state.lastProgressAt = Date.now();
  state.elapsed = 0;
  state.result = null;
  nodes.logPanel.innerHTML = "";
  nodes.logCount.textContent = "0 lines";
  nodes.cadBtn.disabled = true;
  nodes.jsonBtn.disabled = true;
  nodes.open2dBtn.disabled = true;
  nodes.open3dBtn.disabled = true;
  renderProgress();
  const start = performance.now();
  const timer = setInterval(() => { state.elapsed = (performance.now() - start) / 1000; renderProgress(); }, 200);
  try {
    const c = cfg();
    const body = { test_data: testData, solver_name: c.solver_name, time_limit_s: c.time_limit_s, options: { x_gap: c.x_gap, y_gap: c.y_gap, phases: { layer1_x_phases: c.layer1_x_phases, layer1_y_phases: c.layer1_y_phases, layer23_x_phases: c.layer23_x_phases, layer23_y_phases: c.layer23_y_phases, layer4_x_phases: c.layer4_x_phases, layer4_y_phases: c.layer4_y_phases } } };
    await streamSolve(body, handleEvent);
  } catch (e) {
    updateStatus("error");
    appendLog(String(e), "err");
    toast("求解失败");
  } finally {
    clearInterval(timer);
  }
}
function handleEvent(event) {
  if (event.event === "progress") {
    state.phase = event.data.phase;
    state.pct = Number(event.data.pct || 0);
    state.targetPct = Math.max(state.targetPct, state.pct);
    state.msg = event.data.msg;
    state.lastProgressAt = Date.now();
    renderProgress();
    return;
  }
  if (event.event === "log") {
    const text = String(event.data);
    nudgeProgressByLog(state);
    appendLog(text, inferLogClass(text));
    return;
  }
  if (event.event === "error") { updateStatus("error"); appendLog(String(event.data), "err"); return; }
  if (event.event === "result") {
    state.result = event.data;
    state.phase = "done";
    state.pct = 100;
    state.targetPct = 100;
    state.visualPct = 100;
    state.msg = "求解完成";
    state.cadUrl = event.data?.cad_download_url || "/download/cad/latest";
    const sc = event.data?.result?.totalSetCount ?? 0;
    updateStatus(sc > 0 ? "optimal" : "time_limit");
    nodes.cadBtn.disabled = !Boolean(event.data?.cad_available);
    nodes.jsonBtn.disabled = false;
    nodes.open2dBtn.disabled = false;
    nodes.open3dBtn.disabled = false;
    nodes.frame2d.srcdoc = event.data?.visualization_html || emptyFrame();
    nodes.frame3d.srcdoc = event.data?.stowage_3d_html || emptyFrame();
    nodes.jsonView.textContent = JSON.stringify(event.data?.result || {}, null, 2);
    renderStats();
    renderProgress();
    toast(nodes.cadBtn.disabled ? "求解完成" : "求解完成，可下载 CAD");
  }
}
function renderProgress() {
  const shown = shownProgress(state);
  nodes.phaseLabel.textContent = `${state.phase} · ${shown}%`;
  nodes.elapsedLabel.textContent = state.elapsed > 0 ? `${state.elapsed.toFixed(1)}s` : "";
  nodes.progressBar.style.width = `${shown}%`;
  nodes.progressMsg.textContent = state.msg;
  nodes.progressHint.textContent = progressHint(state);
}
function appendLog(text, cls) {
  state.logQueue.push({ text, cls });
  if (state.flushPending) return;
  state.flushPending = true;
  requestAnimationFrame(() => flushLogs(nodes, state));
  setTimeout(() => { if (state.flushPending) flushLogs(nodes, state); }, 50);
}
function renderStats() {
  const r = state.result;
  const kpis = [{ l: "totalSetCount", v: r?.result?.totalSetCount ?? "—" }, { l: "placements", v: r?.result?.cargoPosition?.length ?? "—" }, { l: "conflicts", v: r?.conflicts_count ?? "—" }, { l: "elapsed", v: r ? `${r.elapsed_seconds.toFixed(1)}s` : "—" }];
  nodes.statsView.innerHTML = kpis.map((k) => `<div class="kpi"><div class="v">${k.v}</div><div class="l">${k.l}</div></div>`).join("");
}
function setTab(tab) {
  nodes.tabs.forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === tab));
  nodes.statsView.classList.toggle("hidden", tab !== "stats");
  nodes.viewer2dWrap.classList.toggle("hidden", tab !== "2d");
  nodes.viewer3dWrap.classList.toggle("hidden", tab !== "3d");
  nodes.jsonView.classList.toggle("hidden", tab !== "json");
}
function updateStatus(status) {
  state.status = status;
  nodes.solveBtn.disabled = status === "running"; nodes.statusBadge.className = `badge status-${status}`;
  nodes.statusBadge.textContent = ({ idle: "Idle", running: "Running", optimal: "Optimal", time_limit: "Time Limit", error: "Error" })[status];
}
function downloadJson() {
  if (!state.result) return;
  const blob = new Blob([JSON.stringify(state.result.result, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = "result.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function emptyFrame() { return "<p style='padding:16px;color:#6b7280'>暂无结果</p>"; }
function toast(text) { nodes.toast.textContent = text; nodes.toast.classList.remove("hidden"); setTimeout(() => nodes.toast.classList.add("hidden"), 1600); }
function tickProgress() { advanceVisualProgress(state); renderProgress(); }
