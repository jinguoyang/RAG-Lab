"""平台 API 客户端。"""
import httpx


class PlatformClient:
    """Reserved for future platform API calls (e.g., RAG queries)."""

    def __init__(self, base_url: str, api_key: str):
        if not api_key:
            raise ValueError(
                "platform_api_key 未配置，请在 .env 中设置 EXT_TRAINING_PLATFORM_API_KEY"
            )
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def create_plan_draft(self, job_title: str, job_description: str) -> dict:
        """调用平台 /training/plans/drafts 生成学习计划。"""
        resp = httpx.post(
            f"{self.base_url}/training/plans/drafts",
            headers=self.headers,
            json={
                "jobTitle": job_title,
                "jobDescription": job_description,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    def list_training_documents(
        self,
        query: str = "",
        category: str | None = None,
        difficulty: str | None = None,
    ) -> list[dict]:
        """调用平台 /training/documents 查询可选文档。"""
        params = []
        if query:
            params.append(("query", query))
        if category:
            params.append(("category", category))
        if difficulty:
            params.append(("difficulty", difficulty))
        query_string = ""
        if params:
            from urllib.parse import urlencode

            query_string = f"?{urlencode(params)}"
        resp = httpx.get(
            f"{self.base_url}/training/documents{query_string}",
            headers=self.headers,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    def create_question_drafts(
        self,
        plan_id: str,
        job_title: str,
        ability_groups: list[str],
        count: int | None = None,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        """调用平台 /training/questions/drafts 生成题目。"""
        payload = {
            "planId": plan_id,
            "jobTitle": job_title,
            "abilityGroups": ability_groups,
            "documentIds": document_ids or [],
        }
        if count is not None:
            payload["count"] = count
        resp = httpx.post(
            f"{self.base_url}/training/questions/drafts",
            headers=self.headers,
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    def grade_subjective_answer(self, payload: dict) -> dict:
        """调用平台主观题评分能力，不传平台题库 questionId。"""
        resp = httpx.post(
            f"{self.base_url}/training/post-quizzes/subjective-grading",
            headers=self.headers,
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    def chat(
        self,
        conversation_id: str,
        query: str,
        inputs: dict | None = None,
    ) -> dict:
        """调用平台 app-runtime/chat-messages 获取 RAG 回答。"""
        payload = {
            "query": query,
            "conversationId": conversation_id,
            "inputs": inputs or {},
        }
        resp = httpx.post(
            f"{self.base_url}/app-runtime/chat-messages",
            headers=self.headers,
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()

    def create_classroom_session(self, payload: dict) -> dict:
        """调用平台员工培训课堂 Agent 创建会话。"""
        resp = httpx.post(
            f"{self.base_url}/training/classroom/sessions",
            headers=self.headers,
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_classroom_session(self, session_id: str) -> dict:
        """调用平台员工培训课堂 Agent 获取会话详情。"""
        resp = httpx.get(
            f"{self.base_url}/training/classroom/sessions/{session_id}",
            headers=self.headers,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    def submit_classroom_event(self, session_id: str, payload: dict) -> dict:
        """调用平台员工培训课堂 Agent 提交事件。"""
        resp = httpx.post(
            f"{self.base_url}/training/classroom/sessions/{session_id}/events",
            headers=self.headers,
            json=payload,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()
