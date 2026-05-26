# Sprint 53: 嵌入页体验 + 运营视图 实现计划

> 归档说明：本计划已被 [员工培训 Agent 与外部培训应用实施计划](./2026-05-26-employee-training-agent-and-external-app.md) 取代。SSE、Markdown 渲染和 P13 运营分析降级为 P2 后续；Sprint 53 当前重排为无 LLM 能力的外部培训应用基线。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking。

**Goal:** 为嵌入页添加流式输出（SSE）和 Markdown 渲染，提升对话体验；为管理端添加调用分析和反馈闭环视图。

**Architecture:** 后端 `chat-messages` 端点增加 `responseMode=streaming` 支持，使用 SSE 推送 token；前端嵌入页使用 `EventSource` 接收流式数据并渲染 Markdown；P13 增加调用统计和反馈分析标签页。

**Tech Stack:** Python, FastAPI (StreamingResponse), SSE, React, TypeScript, react-markdown

---

## 文件结构

### Task 1-3: 流式输出

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `backend/app/api/routes/app_runtime.py` | SSE 流式响应端点 |
| Modify | `backend/app/services/app_runtime_service.py` | `chat_with_app_runtime` 流式模式 |
| Modify | `backend/app/services/qa_providers.py` | `HttpLlmProvider` 增加 `stream_chat` 方法 |
| Modify | `frontend/src/app/services/appRuntimeService.ts` | SSE 客户端 |
| Modify | `frontend/src/app/pages/P20_EmbeddedRuntime.tsx` | 流式渲染 |

### Task 4-5: Markdown 渲染

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `frontend/src/app/pages/P20_EmbeddedRuntime.tsx` | 安装并使用 react-markdown |
| Modify | `frontend/package.json` | 添加 react-markdown 依赖 |

### Task 6-7: 运营视图

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `backend/app/api/routes/rag_apps.py` | 新增调用统计接口 |
| Modify | `backend/app/services/rag_app_service.py` | 调用统计聚合逻辑 |
| Modify | `frontend/src/app/pages/P13_RagAppManagement.tsx` | 调用分析标签页 |
| Modify | `frontend/src/app/services/ragAppService.ts` | 调用统计 API |
| Modify | `frontend/src/app/types/ragApp.ts` | 统计类型定义 |

---

## Task 1: 流式输出 — 后端 `HttpLlmProvider.stream_chat`

**Files:**
- Modify: `backend/app/services/qa_providers.py`
- Test: `backend/app/tests/unit/test_stream_chat.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/app/tests/unit/test_stream_chat.py
"""流式 LLM 输出测试。"""
from unittest.mock import MagicMock, patch

from app.services.qa_providers import HttpLlmProvider


class TestStreamChat:
    @patch("app.services.qa_providers.httpx.stream")
    def test_stream_chat_yields_tokens(self, mock_stream):
        """stream_chat 应逐 token yield 内容。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        # 模拟 SSE 行
        mock_response.iter_lines.return_value = [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" World"}}]}',
            'data: [DONE]',
        ]
        mock_stream.return_value.__enter__ = MagicMock(return_value=mock_response)
        mock_stream.return_value.__exit__ = MagicMock(return_value=False)

        settings = MagicMock()
        settings.llm_endpoint = "http://test"
        settings.llm_api_key = "key"
        settings.llm_model = "gpt-4"
        provider = HttpLlmProvider(settings)

        tokens = list(provider.stream_chat([{"role": "user", "content": "hi"}]))
        assert tokens == ["Hello", " World"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_stream_chat.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `stream_chat` 方法**

在 `HttpLlmProvider` 类中添加：

```python
def stream_chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 2048):
    """流式输出 LLM 回答，逐 token yield。"""
    import httpx as _httpx

    payload = {
        "model": self._model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    with _httpx.stream("POST", self._endpoint, json=payload, headers=headers, timeout=120) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            try:
                chunk = _httpx.Response(200, text=data).json()
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
            except Exception:
                continue
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_stream_chat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/qa_providers.py backend/app/tests/unit/test_stream_chat.py
git commit -m "feat: add stream_chat method to HttpLlmProvider for SSE streaming"
```

---

## Task 2: 流式输出 — 后端 SSE 端点

**Files:**
- Modify: `backend/app/api/routes/app_runtime.py`
- Modify: `backend/app/services/app_runtime_service.py`

- [ ] **Step 1: 在 `app_runtime_service.py` 中添加流式 chat 函数**

```python
def chat_with_app_runtime_stream(session: Session, credential: str, request: AppRuntimeChatRequest):
    """流式模式的 chat，yield SSE 事件。"""
    from starlette.responses import StreamingResponse
    import json

    now = datetime.now(UTC)
    context = _resolve_runtime_context(session, credential, request, now, _new_started_counter())
    conversation_id = _get_or_create_conversation(session, context.app_row, request, now)
    user_message = _insert_message(session, conversation_id, "user", request.query, "active", now)
    session.commit()

    # 获取检索结果
    provider_set = _build_provider_set()
    revision_id = context.revision_id
    # ... 检索逻辑同 chat_with_app_runtime

    # 构建 prompt（含历史）
    chat_history = []
    if conversation_id:
        history_rows = _read_conversation_history(session, conversation_id, max_turns=5)
        chat_history = [{"role": r["role"], "content": r["content"]} for r in history_rows]

    evidence_text = "\n".join(f"[{i}] {c.content}" for i, c in enumerate(evidence, start=1))
    messages = [{"role": "system", "content": "Answer using only the provided evidence."}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": f"Question: {request.query}\nEvidence:\n{evidence_text}"})

    def event_generator():
        full_answer = []
        for token in provider_set.llm.stream_chat(messages):
            full_answer.append(token)
            yield f"data: {json.dumps({'token': token})}\n\n"
        # 写入 assistant message
        answer_text = "".join(full_answer)
        # ... 写入 app_messages 和 qa_runs
        yield f"data: {json.dumps({'done': True, 'answer': answer_text})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- [ ] **Step 2: 在路由中添加流式端点**

在 `app_runtime.py` 中修改 `chat-messages` 端点，根据 `responseMode` 分流：

```python
@router.post("/chat-messages")
def create_chat_message(request: AppRuntimeChatRequest, ...):
    credential = _extract_bearer_token(authorization)
    if request.responseMode == "streaming":
        return chat_with_app_runtime_stream(session, credential, request)
    return chat_with_app_runtime(session, credential, request)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/routes/app_runtime.py backend/app/services/app_runtime_service.py
git commit -m "feat: add SSE streaming endpoint for chat-messages"
```

---

## Task 3: 流式输出 — 前端 SSE 客户端 + 流式渲染

**Files:**
- Modify: `frontend/src/app/services/appRuntimeService.ts`
- Modify: `frontend/src/app/pages/P20_EmbeddedRuntime.tsx`

- [ ] **Step 1: 在 `appRuntimeService.ts` 中添加流式调用**

```typescript
export async function chatWithAppRuntimeStream(
    token: string,
    request: AppRuntimeChatRequest,
    onToken: (token: string) => void,
    onDone: (response: AppRuntimeChatResponse) => void,
    onError: (error: Error) => void,
): Promise<void> {
    const baseUrl = getApiBaseUrl();
    const response = await fetch(`${baseUrl}/app-runtime/chat-messages`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ ...request, responseMode: "streaming" }),
    });

    if (!response.ok) {
        onError(new Error(`HTTP ${response.status}`));
        return;
    }

    const reader = response.body?.getReader();
    if (!reader) { onError(new Error("No reader")); return; }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
                const data = JSON.parse(line.slice(6));
                if (data.token) onToken(data.token);
                if (data.done) onDone(data);
            } catch { /* skip */ }
        }
    }
}
```

- [ ] **Step 2: 改造 `P20_EmbeddedRuntime.tsx` 的 `runChat`**

```typescript
const [streamingContent, setStreamingContent] = useState("");
const [isStreaming, setIsStreaming] = useState(false);

const runChat = async () => {
    if (!query.trim()) return;
    const userMsg = { role: "user", content: query.trim() };
    setMessages(prev => [...prev, userMsg]);
    setQuery("");
    setIsStreaming(true);
    setStreamingContent("");

    await chatWithAppRuntimeStream(
        token,
        { query: userMsg.content, conversationId, responseMode: "streaming" },
        (token) => setStreamingContent(prev => prev + token),
        (data) => {
            setConversationId(data.conversationId);
            setMessages(prev => [...prev, { role: "assistant", content: streamingContent + (data.answer || "") }]);
            setStreamingContent("");
            setIsStreaming(false);
        },
        (err) => {
            setMessages(prev => [...prev, { role: "assistant", content: "请求失败，请重试。" }]);
            setIsStreaming(false);
        },
    );
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/services/appRuntimeService.ts frontend/src/app/pages/P20_EmbeddedRuntime.tsx
git commit -m "feat: SSE streaming client and real-time token rendering in embedded page"
```

---

## Task 4: Markdown 渲染 — 安装依赖

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/app/pages/P20_EmbeddedRuntime.tsx`

- [ ] **Step 1: 安装 react-markdown**

Run: `cd frontend && npm install react-markdown`
Expected: `react-markdown` 出现在 `package.json` 的 dependencies 中

- [ ] **Step 2: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add react-markdown dependency"
```

---

## Task 5: Markdown 渲染 — 应用到消息展示

**Files:**
- Modify: `frontend/src/app/pages/P20_EmbeddedRuntime.tsx`

- [ ] **Step 1: 在消息渲染处使用 ReactMarkdown**

```tsx
import ReactMarkdown from "react-markdown";

// 在消息列表渲染处:
{messages.map((msg, i) => (
    <div key={i} className={`mb-3 ${msg.role === "user" ? "text-right" : "text-left"}`}>
        <div className={`inline-block max-w-[85%] rounded-lg px-3 py-2 text-sm ${
            msg.role === "user" ? "bg-terracotta text-white" : "bg-white border border-border-cream"
        }`}>
            {msg.role === "assistant" ? (
                <ReactMarkdown className="prose prose-sm max-w-none">{msg.content}</ReactMarkdown>
            ) : (
                msg.content
            )}
        </div>
    </div>
))}

// 流式内容也用 Markdown 渲染:
{isStreaming && streamingContent && (
    <div className="mb-3 text-left">
        <div className="inline-block max-w-[85%] rounded-lg border border-border-cream bg-white px-3 py-2 text-sm">
            <ReactMarkdown className="prose prose-sm max-w-none">{streamingContent}</ReactMarkdown>
        </div>
    </div>
)}
```

- [ ] **Step 2: 运行前端构建验证**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/pages/P20_EmbeddedRuntime.tsx
git commit -m "feat: render assistant messages as Markdown in embedded page"
```

---

## Task 6: 运营视图 — 后端调用统计接口

**Files:**
- Modify: `backend/app/api/routes/rag_apps.py`
- Modify: `backend/app/services/rag_app_service.py`
- Test: `backend/app/tests/unit/test_app_analytics.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/app/tests/unit/test_app_analytics.py
"""应用运营统计测试。"""
from unittest.mock import MagicMock
from uuid import uuid4

from app.services.rag_app_service import get_app_analytics


class TestAppAnalytics:
    def test_returns_call_stats(self):
        """应返回指定时间范围内的调用统计。"""
        mock_session = MagicMock()
        # mock 查询结果
        mock_session.execute.return_value.scalar.return_value = 42
        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"date": "2026-05-20", "count": 10},
            {"date": "2026-05-21", "count": 15},
            {"date": "2026-05-22", "count": 17},
        ]

        result = get_app_analytics(mock_session, uuid4(), days=7)
        assert "totalCalls" in result
        assert "dailyCalls" in result
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_app_analytics.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `get_app_analytics`**

```python
def get_app_analytics(session: Session, app_id: UUID, days: int = 7) -> dict:
    """获取应用运营统计：调用量、响应时间、反馈分布。"""
    from datetime import timedelta
    now = datetime.now(UTC)
    since = now - timedelta(days=days)

    # 总调用量
    total_calls = session.execute(
        select(func.count())
        .select_from(app_messages)
        .join(app_conversations, app_messages.c.conversation_id == app_conversations.c.conversation_id)
        .where(
            app_conversations.c.app_id == app_id,
            app_messages.c.role == "user",
            app_messages.c.created_at >= since,
        )
    ).scalar() or 0

    # 按日统计
    daily_rows = session.execute(
        select(
            func.date(app_messages.c.created_at).label("date"),
            func.count().label("count"),
        )
        .select_from(app_messages)
        .join(app_conversations, app_messages.c.conversation_id == app_conversations.c.conversation_id)
        .where(
            app_conversations.c.app_id == app_id,
            app_messages.c.role == "user",
            app_messages.c.created_at >= since,
        )
        .group_by(func.date(app_messages.c.created_at))
        .order_by(func.date(app_messages.c.created_at))
    ).mappings().all()

    # 反馈分布
    feedback_rows = session.execute(
        select(
            qa_runs.c.feedback_status,
            func.count().label("count"),
        )
        .select_from(qa_runs)
        .where(
            qa_runs.c.app_id == app_id,
            qa_runs.c.created_at >= since,
            qa_runs.c.feedback_status.isnot(None),
        )
        .group_by(qa_runs.c.feedback_status)
    ).mappings().all()

    return {
        "totalCalls": total_calls,
        "dailyCalls": [{"date": str(r["date"]), "count": r["count"]} for r in daily_rows],
        "feedbackDistribution": {r["feedback_status"]: r["count"] for r in feedback_rows},
        "periodDays": days,
    }
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_app_analytics.py -v`
Expected: PASS

- [ ] **Step 5: 添加路由**

在 `rag_apps.py` 中添加：

```python
@router.get("/{app_id}/analytics", response_model=dict)
def get_app_analytics_endpoint(app_id: UUID, days: int = 7, ...):
    return get_app_analytics(session, app_id, days)
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/rag_apps.py backend/app/services/rag_app_service.py backend/app/tests/unit/test_app_analytics.py
git commit -m "feat: add app analytics endpoint with daily call stats and feedback distribution"
```

---

## Task 7: 运营视图 — 前端调用分析标签页

**Files:**
- Modify: `frontend/src/app/services/ragAppService.ts`
- Modify: `frontend/src/app/types/ragApp.ts`
- Modify: `frontend/src/app/pages/P13_RagAppManagement.tsx`

- [ ] **Step 1: 添加类型和 API**

```typescript
// ragApp.ts
export interface AppAnalytics {
    totalCalls: number;
    dailyCalls: Array<{ date: string; count: number }>;
    feedbackDistribution: Record<string, number>;
    periodDays: number;
}

// ragAppService.ts
export async function getAppAnalytics(appId: string, days: number = 7): Promise<AppAnalytics> {
    return apiGet<AppAnalytics>(`/rag-apps/${appId}/analytics?days=${days}`);
}
```

- [ ] **Step 2: 在 P13 应用详情中添加"调用分析"标签**

在应用详情的标签页区域添加一个新的标签：

```tsx
{/* 调用分析标签 */}
{selectedApp && (
    <div className="mt-4">
        <h3 className="text-sm font-medium text-near-black mb-3">调用分析（近 7 天）</h3>
        {analytics ? (
            <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border border-border-cream p-3">
                        <div className="text-2xl font-bold text-near-black">{analytics.totalCalls}</div>
                        <div className="text-xs text-stone-gray">总调用次数</div>
                    </div>
                    <div className="rounded-lg border border-border-cream p-3">
                        <div className="text-2xl font-bold text-near-black">
                            {analytics.dailyCalls.length > 0
                                ? Math.round(analytics.totalCalls / analytics.dailyCalls.length)
                                : 0}
                        </div>
                        <div className="text-xs text-stone-gray">日均调用</div>
                    </div>
                </div>
                {/* 简易柱状图 */}
                <div className="flex items-end gap-1 h-20">
                    {analytics.dailyCalls.map((d) => (
                        <div key={d.date} className="flex-1 flex flex-col items-center">
                            <div
                                className="w-full bg-terracotta rounded-t"
                                style={{ height: `${Math.max(4, (d.count / Math.max(...analytics.dailyCalls.map(x => x.count), 1)) * 100)}%` }}
                            />
                            <span className="text-[10px] text-stone-gray mt-1">{d.date.slice(5)}</span>
                        </div>
                    ))}
                </div>
                {/* 反馈分布 */}
                {Object.keys(analytics.feedbackDistribution).length > 0 && (
                    <div>
                        <h4 className="text-xs font-medium text-stone-gray mb-1">反馈分布</h4>
                        <div className="flex gap-2 flex-wrap">
                            {Object.entries(analytics.feedbackDistribution).map(([status, count]) => (
                                <span key={status} className="text-xs rounded-full border border-border-cream px-2 py-0.5">
                                    {status}: {count}
                                </span>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        ) : (
            <div className="text-sm text-stone-gray">加载中...</div>
        )}
    </div>
)}
```

- [ ] **Step 3: 在组件加载时获取数据**

```typescript
const [analytics, setAnalytics] = useState<AppAnalytics | null>(null);

useEffect(() => {
    if (selectedApp) {
        getAppAnalytics(selectedApp.appId, 7).then(setAnalytics).catch(() => {});
    }
}, [selectedApp]);
```

- [ ] **Step 4: 运行前端构建验证**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/types/ragApp.ts frontend/src/app/services/ragAppService.ts frontend/src/app/pages/P13_RagAppManagement.tsx
git commit -m "feat: add call analytics tab with daily chart and feedback distribution in P13"
```

---

## 验证命令

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests/unit/test_stream_chat.py -v
conda run -n rag-lab pytest app/tests/unit/test_app_analytics.py -v

cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

## 完成标准

- 嵌入页问答支持流式输出，逐 token 打字机效果
- 助理消息以 Markdown 格式渲染，支持列表、加粗、代码块
- P13 应用详情展示调用分析：总调用、日均、按日柱状图、反馈分布
- 所有新代码有对应单元测试
- 前端构建无报错
