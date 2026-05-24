# Sprint 51: 语义检索 + LLM 测验生成 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 retrieve 接口从 ILIKE 文本匹配升级为 Milvus 向量语义检索，并将培训测验生成从硬编码模板替换为 LLM 驱动的智能出题。

**Architecture:** 复用现有 `EmbeddingProvider` + `DenseRetrievalProvider`（Milvus）基础设施，改造 `retrieve_app_runtime_evidence` 函数；复用现有 `HttpLlmProvider._chat()` 调用链，改造 `_build_training_quiz` 和 `_build_structured_output`。

**Tech Stack:** Python, FastAPI, SQLAlchemy, pymilvus, httpx, PostgreSQL, React, TypeScript

---

## 文件结构

### Task 1-3: 语义检索

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `backend/app/services/app_runtime_service.py` | `retrieve_app_runtime_evidence` 改为向量检索 |
| Modify | `backend/app/services/app_runtime_service.py` | 新增 `_build_provider_set` 辅助函数 |
| Create | `backend/app/tests/unit/test_semantic_retrieve.py` | 语义检索单元测试 |

### Task 4-6: LLM 测验生成

| 操作 | 文件 | 职责 |
|------|------|------|
| Modify | `backend/app/services/app_runtime_service.py` | `_build_training_quiz` 改为 LLM 生成 |
| Modify | `backend/app/services/app_runtime_service.py` | `_build_structured_output` 讲解增强 |
| Modify | `backend/app/services/app_runtime_service.py` | 新增 `_generate_quiz_with_llm` 和 `_generate_explain_with_llm` |
| Create | `backend/app/tests/unit/test_llm_quiz_generation.py` | LLM 测验生成单元测试 |
| Create | `backend/app/tests/unit/test_llm_explain_generation.py` | LLM 讲解生成单元测试 |

---

## Task 1: 语义检索 — 添加 Provider 构建辅助函数

**Files:**
- Modify: `backend/app/services/app_runtime_service.py`
- Test: `backend/app/tests/unit/test_semantic_retrieve.py`

**背景:** 当前 `retrieve_app_runtime_evidence` 直接用 PostgreSQL ILIKE 查询。需要改为：先调用 EmbeddingProvider 生成查询向量，再调用 DenseRetrievalProvider 从 Milvus 检索。现有 `qa_run_service.py` 中已有完整调用链可参考。

- [ ] **Step 1: 写失败测试 — `test_semantic_retrieve_returns_milvus_results`**

```python
# backend/app/tests/unit/test_semantic_retrieve.py
"""语义检索测试：验证 retrieve 接口使用向量检索替代 ILIKE。"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.app_runtime_service import retrieve_app_runtime_evidence


def _make_mock_context(kb_id=None):
    ctx = MagicMock()
    ctx.kb_row = {"kb_id": kb_id or uuid4()}
    ctx.app_row = {"app_id": uuid4()}
    return ctx


class TestSemanticRetrieve:
    """retrieve_app_runtime_evidence 应使用 EmbeddingProvider + DenseRetrievalProvider。"""

    @patch("app.services.app_runtime_service._resolve_runtime_context_without_quota")
    @patch("app.services.app_runtime_service.get_qa_run_providers")
    def test_retrieve_uses_vector_search(self, mock_providers, mock_ctx):
        """当 dense_retrieval_provider != local 时，应走 Milvus 向量检索。"""
        from app.schemas.app_runtime import AppRuntimeRetrieveRequest

        mock_ctx.return_value = _make_mock_context()

        # mock embedding provider
        mock_embedding = MagicMock()
        mock_embedding.embed_query.return_value = [0.1] * 1536

        # mock dense provider
        mock_dense = MagicMock()
        candidate = MagicMock()
        candidate.chunk_id = str(uuid4())
        candidate.content = "test content"
        candidate.metadata = {"chunk_index": 0}
        mock_dense.retrieve.return_value = [candidate]

        mock_provider_set = MagicMock()
        mock_provider_set.embedding = mock_embedding
        mock_provider_set.dense = mock_dense
        mock_providers.return_value = mock_provider_set

        # mock session for fallback metadata query
        mock_session = MagicMock()
        mock_session.execute.return_value.mappings.return_value.all.return_value = []
        mock_session.execute.return_value.mappings.return_value.one.return_value = {
            "chunk_id": uuid4(), "chunk_index": 0,
            "content": "test content", "metadata": {},
        }

        request = AppRuntimeRetrieveRequest(query="test query", topK=5)
        # 传入 settings mock 让函数判断 provider 类型
        with patch("app.services.app_runtime_service.get_settings") as mock_settings:
            mock_settings.return_value.dense_retrieval_provider = "milvus"
            mock_settings.return_value.provider_top_k = 5
            # 函数内部应调用 embedding.embed_query 和 dense.retrieve
            # 具体实现见 Step 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_semantic_retrieve.py -v`
Expected: FAIL（函数尚不支持向量检索路径）

- [ ] **Step 3: 在 `app_runtime_service.py` 中添加 `_build_provider_set` 辅助函数**

在 `_resolve_runtime_context_without_quota` 函数之后添加：

```python
def _build_provider_set():
    """构建 QA Run Provider 集合（延迟导入避免循环依赖）。"""
    from app.services.qa_providers import get_qa_run_providers
    from app.core.config import get_settings
    return get_qa_run_providers(get_settings())
```

- [ ] **Step 4: 运行测试确认辅助函数可导入**

Run: `cd backend && conda run -n rag-lab python -c "from app.services.app_runtime_service import _build_provider_set"`
Expected: 无报错

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/app_runtime_service.py backend/app/tests/unit/test_semantic_retrieve.py
git commit -m "feat: add _build_provider_set helper and semantic retrieve test skeleton"
```

---

## Task 2: 语义检索 — 改造 `retrieve_app_runtime_evidence`

**Files:**
- Modify: `backend/app/services/app_runtime_service.py:857-905`
- Test: `backend/app/tests/unit/test_semantic_retrieve.py`

**核心改动:** 当 `dense_retrieval_provider != "local"` 时，走 Milvus 向量检索路径；否则回退到现有 ILIKE。

- [ ] **Step 1: 写失败测试 — `test_retrieve_falls_back_to_ilike_when_local`**

```python
@patch("app.services.app_runtime_service._resolve_runtime_context_without_quota")
def test_retrieve_falls_back_to_ilike_when_local(self, mock_ctx):
    """当 dense_retrieval_provider == local 时，应回退到 ILIKE。"""
    from app.schemas.app_runtime import AppRuntimeRetrieveRequest

    mock_ctx.return_value = _make_mock_context()
    mock_session = MagicMock()
    mock_row = {"chunk_id": uuid4(), "chunk_index": 0, "content": "test", "metadata": {}}
    mock_session.execute.return_value.mappings.return_value.all.return_value = [mock_row]

    request = AppRuntimeRetrieveRequest(query="test", topK=5)
    with patch("app.services.app_runtime_service.get_settings") as mock_settings:
        mock_settings.return_value.dense_retrieval_provider = "local"
        result = retrieve_app_runtime_evidence(mock_session, "cred", request)
        assert len(result.evidences) == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_semantic_retrieve.py::TestSemanticRetrieve::test_retrieve_falls_back_to_ilike_when_local -v`
Expected: FAIL

- [ ] **Step 3: 改造 `retrieve_app_runtime_evidence` 函数**

将函数体替换为：

```python
def retrieve_app_runtime_evidence(
    session: Session,
    credential: str,
    request: AppRuntimeRetrieveRequest,
) -> AppRuntimeRetrieveResponse:
    """从当前 App 所属知识库读取授权证据摘要。优先使用向量语义检索，回退到 ILIKE。"""
    now = datetime.now(UTC)
    context = _resolve_runtime_context_without_quota(session, credential, now)

    from app.core.config import get_settings
    settings = get_settings()

    if settings.dense_retrieval_provider != "local" and request.query.strip():
        # 向量语义检索路径
        provider_set = _build_provider_set()
        embedding = provider_set.embedding.embed_query(request.query.strip())
        candidates = provider_set.dense.retrieve(
            context.kb_row["kb_id"], request.query.strip(), embedding, request.topK,
        )
        # 回表读取 chunk 详情
        chunk_ids = [c.chunk_id for c in candidates]
        if chunk_ids:
            rows = session.execute(
                select(chunks.c.chunk_id, chunks.c.chunk_index, chunks.c.content, chunks.c.metadata)
                .where(chunks.c.chunk_id.in_(chunk_ids), chunks.c.status == "active")
            ).mappings().all()
            row_map = {str(r["chunk_id"]): r for r in rows}
            ordered_rows = [row_map[cid] for cid in chunk_ids if cid in row_map]
        else:
            ordered_rows = []
    else:
        # ILIKE 回退路径
        stmt = (
            select(chunks.c.chunk_id, chunks.c.chunk_index, chunks.c.content, chunks.c.metadata)
            .where(
                chunks.c.kb_id == context.kb_row["kb_id"],
                chunks.c.status == "active",
            )
        )
        if request.query.strip():
            stmt = stmt.where(chunks.c.content.ilike(f"%{request.query.strip()}%"))
        stmt = stmt.order_by(chunks.c.chunk_index.asc()).limit(request.topK)
        ordered_rows = session.execute(stmt).mappings().all()

    evidences = [
        AppRuntimeRetrievedEvidenceDTO(
            evidenceId=str(uuid4()),
            chunkId=str(row["chunk_id"]),
            label=f"片段 {index}",
            summary=_summarize_evidence_content(row["content"]),
            locationSnapshot={
                "chunkId": str(row["chunk_id"]),
                "chunkIndex": row["chunk_index"],
                "source": "milvus" if settings.dense_retrieval_provider != "local" else "postgres_chunks",
            },
        )
        for index, row in enumerate(ordered_rows, start=1)
    ]
    return AppRuntimeRetrieveResponse(
        appId=str(context.app_row["app_id"]),
        kbId=str(context.kb_row["kb_id"]),
        evidences=evidences,
        metadata={
            "queryLength": len(request.query),
            "topK": request.topK,
            "retrievalMode": "vector" if settings.dense_retrieval_provider != "local" else "ilike",
            "authType": "embedToken" if credential.startswith(EMBED_TOKEN_PREFIX) else "apiKey",
        },
    )
```

- [ ] **Step 4: 运行全部语义检索测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_semantic_retrieve.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/app_runtime_service.py backend/app/tests/unit/test_semantic_retrieve.py
git commit -m "feat: upgrade retrieve endpoint to use Milvus vector search with ILIKE fallback"
```

---

## Task 3: 语义检索 — 集成验证

**Files:**
- Test: `backend/app/tests/unit/test_semantic_retrieve.py`

- [ ] **Step 1: 补充边界测试**

```python
@patch("app.services.app_runtime_service._resolve_runtime_context_without_quota")
@patch("app.services.app_runtime_service.get_qa_run_providers")
def test_retrieve_empty_query_skips_vector(self, mock_providers, mock_ctx):
    """空 query 不应调用 embedding，直接返回 topK 结果。"""
    mock_ctx.return_value = _make_mock_context()
    mock_session = MagicMock()
    mock_session.execute.return_value.mappings.return_value.all.return_value = []

    request = AppRuntimeRetrieveRequest(query="   ", topK=5)
    with patch("app.services.app_runtime_service.get_settings") as mock_settings:
        mock_settings.return_value.dense_retrieval_provider = "milvus"
        result = retrieve_app_runtime_evidence(mock_session, "cred", request)
        mock_providers.assert_not_called()
        assert result.metadata["retrievalMode"] == "ilike"


@patch("app.services.app_runtime_service._resolve_runtime_context_without_quota")
@patch("app.services.app_runtime_service.get_qa_run_providers")
def test_retrieve_milvus_empty_results(self, mock_providers, mock_ctx):
    """Milvus 返回空结果时，evidences 应为空列表。"""
    mock_ctx.return_value = _make_mock_context()
    mock_embedding = MagicMock()
    mock_embedding.embed_query.return_value = [0.1] * 1536
    mock_dense = MagicMock()
    mock_dense.retrieve.return_value = []
    mock_provider_set = MagicMock()
    mock_provider_set.embedding = mock_embedding
    mock_provider_set.dense = mock_dense
    mock_providers.return_value = mock_provider_set

    mock_session = MagicMock()
    request = AppRuntimeRetrieveRequest(query="nonexistent", topK=5)
    with patch("app.services.app_runtime_service.get_settings") as mock_settings:
        mock_settings.return_value.dense_retrieval_provider = "milvus"
        result = retrieve_app_runtime_evidence(mock_session, "cred", request)
        assert result.evidences == []
        assert result.metadata["retrievalMode"] == "vector"
```

- [ ] **Step 2: 运行全部测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_semantic_retrieve.py -v`
Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/tests/unit/test_semantic_retrieve.py
git commit -m "test: add edge case tests for semantic retrieve"
```

---

## Task 4: LLM 测验生成 — 添加 `_generate_quiz_with_llm`

**Files:**
- Modify: `backend/app/services/app_runtime_service.py`
- Test: `backend/app/tests/unit/test_llm_quiz_generation.py`

**核心改动:** 用 LLM 生成基于真实培训内容的测验题目，替换硬编码模板。

- [ ] **Step 1: 写失败测试 — `test_llm_quiz_generation_produces_valid_structure`**

```python
# backend/app/tests/unit/test_llm_quiz_generation.py
"""LLM 测验生成测试。"""
from unittest.mock import MagicMock, patch
import json

import pytest

from app.services.app_runtime_service import _generate_quiz_with_llm


class TestLLMQuizGeneration:
    """_generate_quiz_with_llm 应调用 LLM 生成结构化测验。"""

    @patch("app.services.app_runtime_service._build_provider_set")
    def test_generates_valid_quiz_json(self, mock_providers):
        """LLM 返回有效 JSON 时，应解析为标准 quiz 结构。"""
        llm_response = json.dumps({
            "questions": [
                {
                    "questionId": "q1",
                    "type": "single_choice",
                    "stem": "根据安全规程，操作前应首先做什么？",
                    "options": ["检查设备状态", "直接开始操作", "通知同事", "记录时间"],
                    "correctAnswer": "检查设备状态",
                    "explanation": "安全规程要求操作前必须先检查设备状态。",
                }
            ]
        }, ensure_ascii=False)

        mock_llm = MagicMock()
        mock_llm._chat.return_value = llm_response
        mock_provider_set = MagicMock()
        mock_provider_set.llm = mock_llm
        mock_providers.return_value = mock_provider_set

        result = _generate_quiz_with_llm("安全操作", "安全规程要求操作前检查设备...", 1, "normal")
        assert "questions" in result
        assert len(result["questions"]) == 1
        assert result["questions"][0]["type"] == "single_choice"
        assert result["questions"][0]["correctAnswer"] == "检查设备状态"

    @patch("app.services.app_runtime_service._build_provider_set")
    def test_llm_invalid_json_falls_back(self, mock_providers):
        """LLM 返回无效 JSON 时，应回退到模板生成。"""
        mock_llm = MagicMock()
        mock_llm._chat.return_value = "not valid json"
        mock_provider_set = MagicMock()
        mock_provider_set.llm = mock_llm
        mock_providers.return_value = mock_provider_set

        result = _generate_quiz_with_llm("topic", "answer", 2, "normal")
        assert "questions" in result
        assert len(result["questions"]) == 2
        # 回退时应使用模板
        assert "培训测验" in result["questions"][0]["stem"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_llm_quiz_generation.py -v`
Expected: FAIL（`_generate_quiz_with_llm` 尚不存在）

- [ ] **Step 3: 实现 `_generate_quiz_with_llm`**

在 `_build_training_quiz` 函数之前添加：

```python
def _generate_quiz_with_llm(topic: str, answer: str, question_count: int, difficulty: str | None) -> dict | None:
    """调用 LLM 生成基于培训内容的测验题目。失败时返回 None 由调用方回退到模板。"""
    try:
        provider_set = _build_provider_set()
        difficulty_hint = {
            "easy": "简单（事实回忆）",
            "hard": "困难（分析综合）",
        }.get(difficulty or "normal", "中等（理解应用）")

        prompt = (
            f"你是一个培训测验出题专家。根据以下培训内容，生成 {question_count} 道单选题。\n\n"
            f"培训主题：{topic}\n"
            f"培训内容：{answer[:2000]}\n"
            f"难度：{difficulty_hint}\n\n"
            f"要求：\n"
            f"1. 每题 4 个选项，只有 1 个正确答案\n"
            f"2. 干扰选项应基于培训内容，不能明显错误\n"
            f"3. 题目应测试对内容的理解，而非简单记忆\n"
            f"4. explanation 应引用培训材料中的具体内容\n\n"
            f"返回 JSON 格式：\n"
            f'{{"questions": [{{"questionId": "q1", "type": "single_choice", "stem": "题目", "options": ["A", "B", "C", "D"], "correctAnswer": "正确选项的完整文本", "explanation": "解释"}}]}}'
        )

        raw = provider_set.llm._chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )

        # 提取 JSON（LLM 可能包裹在 markdown code block 中）
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(text)
        questions = parsed.get("questions", [])
        if not questions:
            return None

        # 标准化字段
        for i, q in enumerate(questions):
            q.setdefault("questionId", f"q{i + 1}")
            q.setdefault("type", "single_choice")

        return {
            "topic": topic,
            "difficulty": difficulty or "normal",
            "questionCount": len(questions),
            "questions": questions,
        }
    except Exception:
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_llm_quiz_generation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/app_runtime_service.py backend/app/tests/unit/test_llm_quiz_generation.py
git commit -m "feat: add LLM-powered quiz generation with template fallback"
```

---

## Task 5: LLM 测验生成 — 改造 `_build_training_quiz`

**Files:**
- Modify: `backend/app/services/app_runtime_service.py:944-970`
- Test: `backend/app/tests/unit/test_llm_quiz_generation.py`

- [ ] **Step 1: 写失败测试 — `test_build_training_quiz_uses_llm_first`**

```python
@patch("app.services.app_runtime_service._generate_quiz_with_llm")
def test_build_training_quiz_uses_llm_first(self, mock_llm):
    """_build_training_quiz 应优先使用 LLM 生成结果。"""
    from app.services.app_runtime_service import _build_training_quiz

    mock_llm.return_value = {
        "topic": "安全操作",
        "difficulty": "normal",
        "questionCount": 1,
        "questions": [{
            "questionId": "q1", "type": "single_choice",
            "stem": "操作前应检查什么？",
            "options": ["设备状态", "天气", "午餐", "心情"],
            "correctAnswer": "设备状态",
            "explanation": "安全规程要求。",
        }],
    }

    result = _build_training_quiz("安全操作", "安全规程内容...", 1, "normal")
    assert result["questions"][0]["stem"] == "操作前应检查什么？"
    mock_llm.assert_called_once()


@patch("app.services.app_runtime_service._generate_quiz_with_llm")
def test_build_training_quiz_falls_back_on_none(self, mock_llm):
    """LLM 返回 None 时，应回退到模板生成。"""
    from app.services.app_runtime_service import _build_training_quiz

    mock_llm.return_value = None
    result = _build_training_quiz("安全操作", "安全规程内容...", 2, "normal")
    assert len(result["questions"]) == 2
    assert "培训测验" in result["questions"][0]["stem"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_llm_quiz_generation.py::TestBuildTrainingQuiz -v`
Expected: FAIL

- [ ] **Step 3: 改造 `_build_training_quiz`**

```python
def _build_training_quiz(topic: str, answer: str, question_count: int, difficulty: str | None) -> dict:
    """基于培训内容生成测验。优先 LLM 生成，回退到模板。"""
    llm_result = _generate_quiz_with_llm(topic, answer, question_count, difficulty)
    if llm_result is not None:
        return llm_result

    # 模板回退
    base_answer = "完成培训并通过测验"
    questions = []
    for index in range(1, question_count + 1):
        correct_answer = base_answer if index == 1 else f"{topic}要点 {index}"
        questions.append(
            {
                "questionId": f"q{index}",
                "type": "single_choice",
                "stem": f"{topic}培训测验 {index}：根据材料，以下哪项最符合要求？",
                "options": [
                    correct_answer,
                    "跳过学习直接上岗",
                    "仅口头确认无需记录",
                    "由他人代为完成",
                ],
                "correctAnswer": correct_answer,
                "explanation": f"依据培训材料，{answer[:80] or topic}",
            }
        )
    return {
        "topic": topic,
        "difficulty": difficulty or "normal",
        "questionCount": question_count,
        "questions": questions,
    }
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_llm_quiz_generation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/app_runtime_service.py backend/app/tests/unit/test_llm_quiz_generation.py
git commit -m "feat: integrate LLM quiz generation into _build_training_quiz with template fallback"
```

---

## Task 6: LLM 讲解增强 — 改造 `_build_structured_output`

**Files:**
- Modify: `backend/app/services/app_runtime_service.py:973-990`
- Test: `backend/app/tests/unit/test_llm_explain_generation.py`

**核心改动:** `training_explain` 分支从简单文本分割改为 LLM 提炼结构化要点。

- [ ] **Step 1: 写失败测试**

```python
# backend/app/tests/unit/test_llm_explain_generation.py
"""LLM 讲解生成测试。"""
from unittest.mock import MagicMock, patch
import json

from app.services.app_runtime_service import _generate_explain_with_llm


class TestLLMExplainGeneration:
    @patch("app.services.app_runtime_service._build_provider_set")
    def test_generates_structured_explanation(self, mock_providers):
        llm_response = json.dumps({
            "summary": "安全操作的核心要点",
            "keyPoints": ["操作前检查设备状态", "佩戴防护装备", "遵守操作流程"],
        }, ensure_ascii=False)

        mock_llm = MagicMock()
        mock_llm._chat.return_value = llm_response
        mock_provider_set = MagicMock()
        mock_provider_set.llm = mock_llm
        mock_providers.return_value = mock_provider_set

        result = _generate_explain_with_llm("安全操作", "安全操作要求操作前检查设备状态，佩戴防护装备...")
        assert result is not None
        assert len(result["keyPoints"]) == 3
        assert "操作前检查" in result["keyPoints"][0]

    @patch("app.services.app_runtime_service._build_provider_set")
    def test_invalid_json_returns_none(self, mock_providers):
        mock_llm = MagicMock()
        mock_llm._chat.return_value = "invalid"
        mock_provider_set = MagicMock()
        mock_provider_set.llm = mock_llm
        mock_providers.return_value = mock_provider_set

        result = _generate_explain_with_llm("topic", "content")
        assert result is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_llm_explain_generation.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 `_generate_explain_with_llm` 并改造 `_build_structured_output`**

在 `_build_structured_output` 之前添加：

```python
def _generate_explain_with_llm(topic: str, answer: str) -> dict | None:
    """调用 LLM 提炼培训讲解的结构化要点。失败时返回 None。"""
    try:
        provider_set = _build_provider_set()
        prompt = (
            f"你是一个培训讲师。请将以下培训内容提炼为结构化讲解。\n\n"
            f"培训主题：{topic}\n"
            f"培训内容：{answer[:3000]}\n\n"
            f"返回 JSON 格式：\n"
            f'{{"summary": "一句话总结", "keyPoints": ["要点1", "要点2", "要点3"]}}\n'
            f"要求：keyPoints 3-5 个，每个不超过 50 字。"
        )
        raw = provider_set.llm._chat(
            [{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1000,
        )
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(text)
        if not parsed.get("summary") or not parsed.get("keyPoints"):
            return None
        return parsed
    except Exception:
        return None


def _build_structured_output(request: AppRuntimeStructuredRunRequest, scenario: dict, answer: str) -> dict:
    """将 QARun 回答转换为培训讲解或测验结构化输出。"""
    if request.action == "training_explain":
        llm_explain = _generate_explain_with_llm(request.topic, answer)
        if llm_explain is not None:
            return {"explanation": {"topic": request.topic, **llm_explain}}
        # 回退到简单分割
        return {
            "explanation": {
                "topic": request.topic,
                "summary": answer[:200],
                "keyPoints": [item.strip() for item in answer.replace("。", "\n").splitlines() if item.strip()][:5],
            }
        }
    return {
        "quiz": _build_training_quiz(
            request.topic,
            answer,
            _training_question_count(request, scenario),
            request.difficulty,
        )
    }
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_llm_explain_generation.py -v`
Expected: PASS

- [ ] **Step 5: 运行全部相关测试确认无回归**

Run: `cd backend && conda run -n rag-lab pytest app/tests/unit/test_semantic_retrieve.py app/tests/unit/test_llm_quiz_generation.py app/tests/unit/test_llm_explain_generation.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/app_runtime_service.py backend/app/tests/unit/test_llm_explain_generation.py
git commit -m "feat: LLM-powered structured explanation with text-splitting fallback"
```

---

## 验证命令

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests/unit/test_semantic_retrieve.py -v
conda run -n rag-lab pytest app/tests/unit/test_llm_quiz_generation.py -v
conda run -n rag-lab pytest app/tests/unit/test_llm_explain_generation.py -v
```

## 完成标准

- `retrieve` 接口在 `dense_retrieval_provider=milvus` 时使用向量语义检索，返回按相关性排序的结果
- `retrieve` 接口在 `dense_retrieval_provider=local` 时回退到 ILIKE
- 培训测验题目由 LLM 基于真实培训内容生成，干扰选项有合理性
- 培训讲解由 LLM 提炼为结构化要点，而非简单文本分割
- LLM 调用失败时均有模板回退，不影响核心功能
- 所有新代码有对应单元测试
