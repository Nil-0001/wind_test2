# Wind Stowage API — 调用方文档

## 1. 启动后端

```bash
pip install -r requirements.txt
python -m src.api
```

启动后浏览器访问 **`http://localhost:8000/`**（不是 `0.0.0.0:8000`！）会看到一个内置 demo 页面，可以直接验证服务是否正常。

> **`0.0.0.0` 只是 server 的"监听全部网卡"绑定地址**，不能在浏览器里直接打开。
> 浏览器请用：
> - `localhost` / `127.0.0.1`：本机访问
> - `<服务器 LAN IP>`：局域网其它设备访问
> - 部署到生产时由 nginx/域名提供 URL

## 2. 接口总览

| 方法 | 路径 | 用途 | 响应类型 |
|---|---|---|---|
| GET  | `/health` | 健康检查 | `application/json` |
| GET  | `/sample` | 内置样例（即 `test_data.json`） | `application/json` |
| GET  | `/` | demo 页面（开发自测用） | `text/html` |
| **POST** | **`/solve`** | **核心接口：求解配载** | **`text/event-stream` (SSE)** |

只有 `/solve` 是真正的算法接口；其它都是辅助。

## 3. POST `/solve` 详解

### 3.1 请求

```
POST http://<host>:8000/solve
Content-Type: application/json

{
  "test_data": { ...test_data.json 的完整 JSON 内容... },
  "time_limit_s": 180,
  "options": {
    "phases": {
      "layer1_x_phases": 1, "layer1_y_phases": 1,
      "layer23_x_phases": 1, "layer23_y_phases": 1,
      "layer4_x_phases": 1, "layer4_y_phases": 1
    },
    "y_gap": 100,
    "x_gap": 500
  }
}
```

| 字段 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `test_data` | ✅ | — | 整个 `test_data.json` 的 JSON 对象（含 `cargoData` 与 `vesselStructure`） |
| `time_limit_s` | ❌ | 180 | **HiGHS 求解器** B&B 阶段最长用时（秒）。**只限求解器主循环，不含 Pyomo 建模和 HiGHS presolve**，实际 wall time = `time_limit_s + 30~60s`（具体见 §3.4）。建议 60–600。 |
| `options.phases.*` | ❌ | 全 1 | 候选位置加密参数。提高 phase 候选更多、解可能更优、求解更慢。 |
| `options.y_gap` | ❌ | 100 | 货物 y 向最小间距（mm） |
| `options.x_gap` | ❌ | 500 | 货物 x 向最小间距（mm） |

### 3.4 `time_limit_s` 精确语义

整个求解流水线分 5 个阶段，**`time_limit_s` 只限制其中一个**：

| 阶段 | 是否被 `time_limit_s` 限制 | 5040 候选下典型耗时 | 大候选(20k+)下典型耗时 |
|---|---|---|---|
| `load`（解析输入） | ❌ | < 0.1s | < 0.5s |
| `candidates`（生成候选位） | ❌ | 0.1s | 1–5s |
| `build`（构建 Pyomo + 冲突对） | ❌ | 10–15s | 1–10 min |
| `solve`（HiGHS 求解器） | ✅ **仅限此阶段** | 30–80s | 视模型而定 |
| `output`（生成 HTML/JSON） | ❌ | 1–3s | 5–20s |

> ⚠️ 早期版本里 `time_limit` 因 pyomo APPSI 接口变更没生效（已修复）。
> 但即使现在生效，**HiGHS 内部 presolve 也不被它限制**（HiGHS 设计如此），所以 `solve` 阶段实际 wall time = `time_limit_s + presolve(20–60s)`。

**对前端的实际意义**：
- 总等待时间 ≈ `build_time + presolve_time + min(solver_time, time_limit_s) + output_time`
- 候选数越大，`build` 阶段越久，**且不被 `time_limit_s` 控制**
- 想严格限制总耗时：减小 `options.phases.*` 即可（默认全 1 已是最经济档位）

### 3.2 响应：Server-Sent Events (SSE)

返回 `Content-Type: text/event-stream`，是一段持续的 HTTP 响应（**不是普通 JSON**），每条事件格式：

```
event: <kind>
data: <JSON 或字符串>

```

每条事件之间用空行隔开。**4 种事件**：

#### `event: progress`（约 10 条/次求解）
```
event: progress
data: {"phase": "candidates", "pct": 25, "msg": "Generated 5040 candidate placements"}
```
- `phase`：阶段标识，依次 `load → candidates → build → solve → output → done`
- `pct`：0–100，对应进度条
- `msg`：人类可读的说明

#### `event: log`（数十至上百条/次求解）
```
event: log
data: "Running HiGHS 1.14.0 (git hash: 7df0786) ..."
```
- `data` 是字符串（一行 HiGHS / pyomo 终端输出）
- 用来在前端做"实时滚动终端"

#### `event: result`（成功时**仅 1 条**，且为最后一条）
```
event: result
data: {
  "result": { "totalSetCount": 24, "cargoPosition": [...], "bypassBoardPosition": [...] },
  "stowage_3d_html": "<!DOCTYPE html>...",
  "visualization_html": "<!DOCTYPE html>...",
  "elapsed_seconds": 87.1,
  "conflicts_count": 0
}
```
- `result`：原始 JSON（即 `result.json` 的完整内容）
- `stowage_3d_html`：3D 可视化 HTML 字符串（可整段 `<iframe srcdoc="...">` 内嵌或写文件）
- `visualization_html`：分层 2D 可视化 HTML 字符串
- `elapsed_seconds`：求解总耗时
- `conflicts_count`：自检发现的几何冲突数（应为 0）

#### `event: error`（失败时唯一的终止事件）
```
event: error
data: "ValueError: missing key 'cargoData' in test_data\nTraceback ..."
```

#### `:heartbeat`（保活，每 10 秒一次）
```
:heartbeat

```
- 只有冒号开头的注释行，无 event/data
- 客户端忽略即可，作用是防止 nginx/CDN 切断空闲长连接

### 3.3 终止条件

收到 **`event: result`** 或 **`event: error`** 后流就结束，server 会主动关闭连接。客户端不需要再读。

---

## 4. 调用方代码模板

### 4.1 浏览器 JavaScript（fetch + ReadableStream）

⚠️ **不能用 `EventSource`**，因为它只支持 GET，而我们的 `/solve` 是 POST（请求体是 JSON）。

```js
async function solveStowage(testData, opts = {}) {
  const resp = await fetch("http://localhost:8000/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      test_data: testData,
      time_limit_s: opts.timeLimit ?? 180,
      options: opts.options,
    }),
  });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    const blocks = buf.split("\n\n");
    buf = blocks.pop();                          // 末尾可能不完整，留到下次

    for (const blk of blocks) {
      if (blk.startsWith(":")) continue;         // heartbeat
      const ev = parseSSE(blk);

      if (ev.event === "progress") {
        progressBar.style.width = ev.data.pct + "%";
        statusLabel.textContent = ev.data.msg;
      } else if (ev.event === "log") {
        terminalDiv.textContent += ev.data + "\n";
        terminalDiv.scrollTop = terminalDiv.scrollHeight;
      } else if (ev.event === "result") {
        showResultJson(ev.data.result);
        viz2dIframe.srcdoc = ev.data.visualization_html;
        viz3dIframe.srcdoc = ev.data.stowage_3d_html;
        return ev.data;                           // 终止
      } else if (ev.event === "error") {
        throw new Error(ev.data);
      }
    }
  }
}

function parseSSE(block) {
  const ev = { event: "message", data: "" };
  for (const line of block.split("\n")) {
    const i = line.indexOf(":");
    if (i < 0) continue;
    const k = line.slice(0, i).trim();
    const v = line.slice(i + 1).trim();
    if (k === "event") ev.event = v;
    else if (k === "data") ev.data = v;
  }
  try { ev.data = JSON.parse(ev.data); } catch (_) { /* keep string */ }
  return ev;
}

// 用法
const testData = await (await fetch("http://localhost:8000/sample")).json();
await solveStowage(testData, { timeLimit: 180 });
```

### 4.2 React 组件示例（关键片段）

```jsx
function StowageDemo() {
  const [pct, setPct] = useState(0);
  const [phase, setPhase] = useState("idle");
  const [logs, setLogs] = useState([]);
  const [result, setResult] = useState(null);

  const run = async (testData) => {
    setLogs([]); setResult(null);
    await solveStowage(testData, {
      onProgress: (d) => { setPct(d.pct); setPhase(d.phase); },
      onLog: (line) => setLogs(L => [...L, line]),
      onResult: (data) => setResult(data),
    });
  };
  // ...
}
```
（把 4.1 里的 `solveStowage` 拆成接受 callback，更适配 React。）

### 4.3 Python 客户端

```python
import json, requests

def solve(test_data: dict, base="http://localhost:8000", time_limit_s=180):
    payload = {"test_data": test_data, "time_limit_s": time_limit_s}
    with requests.post(f"{base}/solve", json=payload, stream=True) as r:
        r.raise_for_status()
        buf = ""
        for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
            buf += chunk
            blocks = buf.split("\n\n")
            buf = blocks.pop()
            for blk in blocks:
                if blk.startswith(":"): continue
                ev = parse_sse(blk)
                if ev["event"] == "progress":
                    print(f"[{ev['data']['phase']:>10}] {ev['data']['pct']:>3}% {ev['data']['msg']}")
                elif ev["event"] == "log":
                    print("  log:", ev["data"])
                elif ev["event"] == "result":
                    return ev["data"]                 # {result, stowage_3d_html, visualization_html, ...}
                elif ev["event"] == "error":
                    raise RuntimeError(ev["data"])

def parse_sse(block):
    ev = {"event": "message", "data": ""}
    for line in block.splitlines():
        if ":" not in line: continue
        k, v = line.split(":", 1)
        ev[k.strip()] = v.strip()
    try:    ev["data"] = json.loads(ev["data"])
    except Exception: pass
    return ev

# 用法
with open("test_data.json", encoding="utf-8") as f:
    td = json.load(f)
out = solve(td, time_limit_s=180)
open("result.json","w",encoding="utf-8").write(json.dumps(out["result"], ensure_ascii=False, indent=2))
open("stowage_3d.html","w",encoding="utf-8").write(out["stowage_3d_html"])
open("visualization.html","w",encoding="utf-8").write(out["visualization_html"])
```

### 4.4 curl（命令行调试）

```bash
# 准备请求体
echo '{"test_data": ' > req.json
cat test_data.json >> req.json
echo ', "time_limit_s": 180}' >> req.json

# -N = 关闭 buffering, 才能实时看到 SSE 事件
curl -N -X POST http://localhost:8000/solve \
  -H "Content-Type: application/json" \
  --data-binary @req.json
```

---

## 5. 常见坑

| 现象 | 原因 | 解法 |
|---|---|---|
| 浏览器 `http://0.0.0.0:8000/` 502 | `0.0.0.0` 不是浏览器可访问的目标地址 | 改用 `http://localhost:8000/` |
| 求解 60s 中途无任何事件 | 代理在缓冲响应（nginx 默认） | nginx 加 `proxy_buffering off; proxy_read_timeout 600s;` |
| `EventSource` 收不到任何事件 | EventSource 仅支持 GET | 改用 `fetch` + `body.getReader()`，见 §4.1 |
| 浏览器报 CORS | 跨域 | server 已经 `allow_origins=["*"]`；如还报错检查代理是否吞掉 CORS 头 |
| 收到 result 后还有事件 | 没有及时 break | 收到 `event:result` 或 `event:error` 后立即 `return`/`reader.cancel()` |
| 大请求被截断 | body 太大（>1MB） | 检查 nginx `client_max_body_size 10m;` |
| SSE 返回看似乱码 | 没设 UTF-8 解码 | 客户端用 `TextDecoder('utf-8')` |

---

## 6. 部署到生产建议

```nginx
# nginx 反代示例
location /solve {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;                # 关键：SSE 必须关
    proxy_cache off;
    proxy_read_timeout 600s;            # 求解最长 10 分钟
    add_header X-Accel-Buffering no;
}
location / {
    proxy_pass http://127.0.0.1:8000;
}
```

进程管理用 systemd / supervisor / docker：
```bash
# Docker 简易示例
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --workers 1
# workers=1 因为求解非常吃内存，多 worker 会撑爆；高并发改成"任务队列 + 多机"
```

---

## 7. 接口速查

```
GET  /health              → {"status":"ok"}
GET  /sample              → test_data.json 内容
POST /solve  body=JSON    → SSE 流 (progress/log/result/error)
GET  /                    → demo HTML（仅开发用）
```
