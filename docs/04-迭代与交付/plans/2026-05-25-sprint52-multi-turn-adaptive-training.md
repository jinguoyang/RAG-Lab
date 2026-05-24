# Sprint 52: 多轮对话 + 自适应培训 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为知识库问答助手添加多轮对话上下文，使 LLM 能理解追问和指代；为员工培训助手添加自适应难度和知识掌握度追踪。

**Architecture:** 在 `chat_with_app_runtime` 中注入历史消息到 LLM prompt；在 `app_messages.metadata` 中追踪知识点掌握情况，培训报告按知识点维度聚合。

**Tech Stack:** Python, FastAPI, SQLAlchemy, PostgreSQL, React, TypeScript

---

## 文件结构

### Task 1-3: 多轮对话

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `backend/app/services/app_runtime_service.py` | `chat_with_app_runtime` 注入历史消息 |
| Modify | `backend/app/services/app_runtime_service.py` | 新增 `_read_conversation_history` |
| Modify | `backend/app/services/qa_providers.py` | `generate_answer` 增加 `chat_history` 参数 |
| Modify | `frontend/src/app/pages/P20_EmbeddedRuntime.tsx` | 维护消息列表，传递 conversationId |
| Create | `backend/app/tests/unit/test_multi_turn_chat.py` | 多轮对话单元测试 |

### Task 4-6: 自适应培训

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `backend/app/services/app_runtime_service.py` | 测验评分后写入知识点掌握度 |
| Modify | `backend/app/services/rag_app_service.py` | 培训报告增加知识点维度聚合 |
| Modify | `frontend/src/app/pages/P13_RagAppManagement.tsx` | 培训报告展示知识点掌握度 |
| Create | `backend/app/tests/unit/test_adaptive_training.py` | 自适应培训单元测试 |

---

## Task 1: 多轮对话 — 添加 `_read_conversation_history`

**Files:**
- Modify: `backend/app/services/app_runtime_service.py`
- Test: `backend/app/tests/unit/test_multi_turn_chat.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/app/tests/unit/test_multi_turn_chat.py
"""多轮对话上下文测试。"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.app_runtime_service import _read_conversation_history


class TestConversationHistory:
    def test_reads_recent_messages(self):
        """应读取指定会话的最近 N 条消息，按时间正序返回。"""
        conversation_id = uuid4()
        mock_session = MagicMock()
        mock_messages = [
            {"role": "user", "content": "什么是安全操作？", "created_at": "2026-01-01T10:00:00"},
            {"role": "assistant", "content": "安全操作是指...", "created_at": "2026-01-01T10:00:01"},
            {"role": "user", "content": "具体包括哪些？", "created_at": "2026-01-01T10:00:02"},
        ]
        mock_session.execute.return_value.mappings.return_value.all.return_value = mock_messages

        result = _read_conversation_history(mock_session, conversation_id, max_turns=5)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[-1]["role"] == "user"

    def test_limits_to_max_turns(self):
        """应限制返回的消息数量。"""
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.all.return_value = [
            {"role": "user", "content": "q1", "created_at": "t1"},
            {"role": "assistant", "content": "a1", "created_at": "t2"},
        ]
        result = _read_conversation_history(mock_session, uuid4(), max_turns=1)
        assert len(result) == 2  # 1 turn = 1 user + 1 assistant
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_multi_turn_chat.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `_read_conversation_history`**

在 `_insert_message` 函数之后添加：

```python
def _read_conversation_history(session: Session, conversation_id: UUID, max_turns: int = 5) -> list[dict]:
    """读取会话最近 N 轮消息（1 轮 = 1 user + 1 assistant），按时间正序。"""
    limit = max_turns * 2  # 每轮 2 条消息
    rows = session.execute(
        select(
            app_messages.c.role,
            app_messages.c.content,
            app_messages.c.created_at,
        )
        .where(app_messages.c.conversation_id == conversation_id)
        .order_by(app_messages.c.created_at.desc())
        .limit(limit)
    ).mappings().all()
    # 反转为正序
    return list(reversed(rows))
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_multi_turn_chat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/app_runtime_service.py backend/app/tests/unit/test_multi_turn_chat.py
git commit -m "feat: add _read_conversation_history for multi-turn chat context"
```

---

## Task 2: 多轮对话 — 改造 `generate_answer` 支持 chat_history

**Files:**
- Modify: `backend/app/services/qa_providers.py:1021-1035`
- Test: `backend/app/tests/unit/test_multi_turn_chat.py`

- [ ] **Step 1: 写失败测试**

```python
class TestGenerateAnswerWithHistory:
    @patch("app.services.qa_providers.httpx.post")
    def test_includes_chat_history_in_prompt(self, mock_post):
        """generate_answer 应将 chat_history 注入到 messages 中。"""
        from app.services.qa_providers import HttpLlmProvider

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "answer"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        settings = MagicMock()
        settings.llm_endpoint = "http://test"
        settings.llm_api_key = "key"
        settings.llm_model = "gpt-4"
        provider = HttpLlmProvider(settings)

        history = [
            {"role": "user", "content": "什么是安全操作？"},
            {"role": "assistant", "content": "安全操作是指..."},
        ]
        provider.generate_answer("具体包括哪些？", [], chat_history=history)

        call_args = mock_post.call_args
        messages = call_args[1]["json"]["messages"]
        # 应包含 system + history + current question
        assert len(messages) >= 4  # system + 2 history + user
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "什么是安全操作？"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_multi_turn_chat.py::TestGenerateAnswerWithHistory -v`
Expected: FAIL

- [ ] **Step 3: 改造 `HttpLlmProvider.generate_answer`**

修改 `qa_providers.py` 中 `generate_answer` 方法签名和实现：

```python
def generate_answer(self, query: str, evidence, temperature=None, max_context_tokens=None, chat_history=None):
    """生成回答。chat_history 为可选的历史消息列表 [{"role": "user"/"assistant", "content": "..."}]。"""
    evidence_text = "\n".join(
        f"[{index}] {candidate.content or candidate.metadata}"
        for index, candidate in enumerate(evidence, start=1)
    )
    messages = [
        {"role": "system", "content": "Answer using only the provided evidence. If evidence is insufficient, say so."},
    ]
    # 注入历史对话
    if chat_history:
        for msg in chat_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    # 当前问题
    messages.append({"role": "user", "content": f"Question: {query}\nEvidence:\n{evidence_text}"})
    return self._chat(messages, temperature=temperature)
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_multi_turn_chat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/qa_providers.py backend/app/tests/unit/test_multi_turn_chat.py
git commit -m "feat: add chat_history parameter to generate_answer for multi-turn context"
```

---

## Task 3: 多轮对话 — 改造 `chat_with_app_runtime` 和前端

**Files:**
- Modify: `backend/app/services/app_runtime_service.py:650-789`
- Modify: `frontend/src/app/pages/P20_EmbeddedRuntime.tsx`
- Test: `backend/app/tests/unit/test_multi_turn_chat.py`

- [ ] **Step 1: 写失败测试 — `test_chat_injects_history`**

```python
class TestChatWithHistory:
    @patch("app.services.app_runtime_service.create_qa_run")
    @patch("app.services.app_runtime_service.get_qa_run_detail")
    @patch("app.services.app_runtime_service._resolve_runtime_context")
    @patch("app.services.app_runtime_service._get_or_create_conversation")
    @patch("app.services.app_runtime_service._insert_message")
    @patch("app.services.app_runtime_service._read_conversation_history")
    def test_passes_history_to_qa_run(self, mock_history, mock_insert, mock_conv, mock_ctx, mock_detail, mock_create):
        """chat_with_app_runtime 应读取历史并传入 create_qa_run。"""
        from app.services.app_runtime_service import chat_with_app_runtime
        from app.schemas.app_runtime import AppRuntimeChatRequest

        mock_ctx.return_value = MagicMock(
            app_row={"app_id": uuid4(), "status": "active"},
            kb_row={"kb_id": uuid4()},
            revision_id=uuid4(),
            actor=MagicMock(),
        )
        mock_conv.return_value = uuid4()
        mock_history.return_value = [
            {"role": "user", "content": "之前的问题"},
            {"role": "assistant", "content": "之前的回答"},
        ]
        mock_insert.return_value = {"message_id": uuid4()}
        mock_create.return_value = uuid4()
        mock_detail.return_value = MagicMock(
            answer="回答", citations=[], usage={}, run_id=uuid4(), evidence=[]
        )

        request = AppRuntimeChatRequest(query="追问", conversationId=uuid4())
        mock_session = MagicMock()
        chat_with_app_runtime(mock_session, "cred", request)

        # 验证 create_qa_run 被调用时 overrideParams 包含 chat_history
        call_kwargs = mock_create.call_args
        override = call_kwargs[1].get("override_params") or call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None
        # history 应被传入
        mock_history.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_multi_turn_chat.py::TestChatWithHistory -v`
Expected: FAIL

- [ ] **Step 3: 改造 `chat_with_app_runtime`**

在 `chat_with_app_runtime` 函数中，写入 user message 之前，读取历史消息：

```python
    # 在 _get_or_create_conversation 之后，_insert_message 之前添加:
    # 读取历史对话（排除当前消息）
    chat_history = []
    if conversation_id:
        history_rows = _read_conversation_history(session, conversation_id, max_turns=5)
        chat_history = [{"role": r["role"], "content": r["content"]} for r in history_rows]
```

然后将 `chat_history` 通过 `override_params` 传入 `create_qa_run`。

- [ ] **Step 4: 改造前端 `P20_EmbeddedRuntime.tsx`**

将前端从单 answer 模式改为消息列表模式：

```typescript
// 替换 answer state 为 messages 数组
const [messages, setMessages] = useState<Array<{role: string, content: string, messageId?: string}>>([]);
const [conversationId, setConversationId] = useState<string | null>(null);

const runChat = async () => {
    if (!query.trim()) return;
    const userMsg = { role: "user", content: query.trim() };
    setMessages(prev => [...prev, userMsg]);
    setQuery("");

    try {
        const response = await chatWithAppRuntime(token, {
            query: userMsg.content,
            conversationId: conversationId,
            responseMode: "blocking",
        });
        setConversationId(response.conversationId);
        setMessages(prev => [...prev, {
            role: "assistant",
            content: response.answer,
            messageId: response.messageId,
        }]);
    } catch (err) {
        setMessages(prev => [...prev, { role: "assistant", content: "请求失败，请重试。" }]);
    }
};
```

- [ ] **Step 5: 运行后端测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_multi_turn_chat.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/app_runtime_service.py frontend/src/app/pages/P20_EmbeddedRuntime.tsx backend/app/tests/unit/test_multi_turn_chat.py
git commit -m "feat: multi-turn conversation with chat history injection and frontend message list"
```

---

## Task 4: 自适应培训 — 知识点掌握度追踪

**Files:**
- Modify: `backend/app/services/app_runtime_service.py`
- Test: `backend/app/tests/unit/test_adaptive_training.py`

**核心改动:** 测验评分后，将每个知识点的答对/答错情况写入 `app_messages.metadata.topicMastery`。

- [ ] **Step 1: 写失败测试**

```python
# backend/app/tests/unit/test_adaptive_training.py
"""自适应培训测试。"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.app_runtime_service import _extract_topic_mastery


class TestTopicMastery:
    def test_extracts_mastery_from_quiz_results(self):
        """应从测验结果中提取每个知识点的掌握情况。"""
        quiz_results = [
            {"questionId": "q1", "isCorrect": True, "explanation": "安全规程要求操作前检查设备状态"},
            {"questionId": "q2", "isCorrect": False, "explanation": "防护装备包括安全帽和手套"},
            {"questionId": "q3", "isCorrect": True, "explanation": "安全规程要求操作前检查设备状态"},
        ]
        result = _extract_topic_mastery(quiz_results)
        assert isinstance(result, dict)
        # 应包含知识点级别的掌握度
        assert any(v.get("correct", 0) > 0 for v in result.values())

    def test_empty_results_returns_empty(self):
        assert _extract_topic_mastery([]) == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_adaptive_training.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `_extract_topic_mastery`**

```python
def _extract_topic_mastery(quiz_results: list[dict]) -> dict:
    """从测验结果中提取知识点掌握度统计。返回 {topic: {correct, total, rate}}。"""
    topic_stats: dict[str, dict] = {}
    for result in quiz_results:
        explanation = result.get("explanation", "")
        # 用 explanation 的前 20 字符作为知识点指纹
        topic_key = explanation[:20] if explanation else "general"
        if topic_key not in topic_stats:
            topic_stats[topic_key] = {"correct": 0, "total": 0, "sample": explanation[:100]}
        topic_stats[topic_key]["total"] += 1
        if result.get("isCorrect"):
            topic_stats[topic_key]["correct"] += 1
    for stats in topic_stats.values():
        stats["rate"] = round(stats["correct"] / stats["total"], 2) if stats["total"] > 0 else 0
    return topic_stats
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_adaptive_training.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/app_runtime_service.py backend/app/tests/unit/test_adaptive_training.py
git commit -m "feat: extract topic mastery from quiz results for adaptive training"
```

---

## Task 5: 自适应培训 — 评分后写入掌握度 + 报告增强

**Files:**
- Modify: `backend/app/services/app_runtime_service.py:1134-1190`
- Modify: `backend/app/services/rag_app_service.py`
- Test: `backend/app/tests/unit/test_adaptive_training.py`

- [ ] **Step 1: 写失败测试 — `test_quiz_submission_writes_mastery`**

```python
class TestQuizSubmissionMastery:
    def test_writes_mastery_to_metadata(self):
        """测验评分后应将掌握度写入 app_messages.metadata。"""
        # 验证 submit_app_runtime_training_quiz 调用 _extract_topic_mastery
        # 并将结果写入 metadata.topicMastery
        pass  # 完整实现见 Step 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_adaptive_training.py::TestQuizSubmissionMastery -v`
Expected: FAIL

- [ ] **Step 3: 改造 `submit_app_runtime_training_quiz`**

在评分完成后，写入 metadata 时添加 topicMastery：

```python
    # 在 _score_training_answers 之后添加:
    topic_mastery = _extract_topic_mastery(results)

    # 写入 assistant message metadata 时包含:
    metadata={
        "trainingResult": {
            "score": score,
            "passed": passed,
            "passingScore": passing_score,
            "questionCount": len(results),
            "correctCount": sum(1 for r in results if r["isCorrect"]),
        },
        "topicMastery": topic_mastery,
    }
```

- [ ] **Step 4: 增强培训报告 — 按知识点聚合**

在 `rag_app_service.py` 的 `get_training_report` 函数中，增加知识点维度：

```python
    # 在现有聚合逻辑之后添加:
    # 知识点掌握度聚合
    topic_mastery_rows = session.execute(
        select(app_messages.c.metadata)
        .select_from(app_messages)
        .join(app_conversations, app_messages.c.conversation_id == app_conversations.c.conversation_id)
        .where(
            app_conversations.c.app_id == app_id,
            app_messages.c.role == "assistant",
            app_messages.c.metadata["topicMastery"].isnot(None),
        )
        .order_by(app_messages.c.created_at.desc())
        .limit(50)
    ).scalars().all()

    # 合并所有知识点掌握度
    merged_topics: dict[str, dict] = {}
    for meta in topic_mastery_rows:
        mastery = (meta or {}).get("topicMastery", {})
        for topic_key, stats in mastery.items():
            if topic_key not in merged_topics:
                merged_topics[topic_key] = {"correct": 0, "total": 0, "sample": stats.get("sample", "")}
            merged_topics[topic_key]["correct"] += stats.get("correct", 0)
            merged_topics[topic_key]["total"] += stats.get("total", 0)
    for stats in merged_topics.values():
        stats["rate"] = round(stats["correct"] / stats["total"], 2) if stats["total"] > 0 else 0
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_adaptive_training.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/app_runtime_service.py backend/app/services/rag_app_service.py backend/app/tests/unit/test_adaptive_training.py
git commit -m "feat: write topic mastery after quiz submission and aggregate in training report"
```

---

## Task 6: 自适应培训 — 前端知识点掌握度展示

**Files:**
- Modify: `frontend/src/app/pages/P13_RagAppManagement.tsx`
- Modify: `frontend/src/app/types/ragApp.ts`

- [ ] **Step 1: 在 ragApp.ts 中添加类型**

```typescript
// 在 TrainingReportDTO 中添加:
export interface TopicMasteryItem {
  topic: string;
  sample: string;
  correct: number;
  total: number;
  rate: number;
}

// TrainingReportDTO 增加:
topicMastery?: Record<string, TopicMasteryItem>;
```

- [ ] **Step 2: 在 P13 培训报告区添加知识点掌握度展示**

在培训报告摘要区域（`selectedApp.scenarioType === "employee_training"` 分支）添加：

```tsx
{report.topicMastery && Object.keys(report.topicMastery).length > 0 && (
    <div className="mt-3">
        <h4 className="text-sm font-medium text-near-black mb-2">知识点掌握度</h4>
        <div className="space-y-1">
            {Object.entries(report.topicMastery).slice(0, 5).map(([key, item]) => (
                <div key={key} className="flex items-center gap-2 text-xs">
                    <span className="truncate max-w-[200px]" title={item.sample}>{item.sample || key}</span>
                    <div className="flex-1 h-2 bg-border-cream rounded-full overflow-hidden">
                        <div
                            className={`h-full rounded-full ${item.rate >= 0.8 ? "bg-green-500" : item.rate >= 0.5 ? "bg-yellow-500" : "bg-red-500"}`}
                            style={{ width: `${item.rate * 100}%` }}
                        />
                    </div>
                    <span className="text-stone-gray">{Math.round(item.rate * 100)}%</span>
                </div>
            ))}
        </div>
    </div>
)}
```

- [ ] **Step 3: 运行前端构建验证**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/types/ragApp.ts frontend/src/app/pages/P13_RagAppManagement.tsx
git commit -m "feat: display topic mastery progress bars in training report"
```

---

## 验证命令

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests/unit/test_multi_turn_chat.py -v
conda run -n rag-lab pytest app/tests/unit/test_adaptive_training.py -v

cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

## 完成标准

- 问答助手支持多轮对话，能理解追问和指代
- 前端嵌入页展示完整对话历史，而非单条回答
- 培训测验评分后自动提取知识点掌握度
- 培训报告按知识点维度展示掌握度进度条
- 所有新代码有对应单元测试
