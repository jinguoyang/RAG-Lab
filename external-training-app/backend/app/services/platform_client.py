"""平台 API 客户端。"""
import httpx


class PlatformClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def create_plan_draft(self, app_id: str, job_title: str, job_description: str) -> dict:
        resp = httpx.post(f"{self.base_url}/training/plans/drafts",
                         json={"appId": app_id, "jobTitle": job_title, "jobDescription": job_description},
                         headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def review_plan_draft(self, draft_id: str, decision: str, notes: str = "") -> dict:
        resp = httpx.post(f"{self.base_url}/training/plans/{draft_id}/review",
                         json={"decision": decision, "notes": notes}, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def create_classroom_session(self, app_id: str, end_user_id: str, plan_id: str | None = None) -> dict:
        resp = httpx.post(f"{self.base_url}/training/classroom/sessions",
                         json={"appId": app_id, "endUserId": end_user_id, "planId": plan_id},
                         headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def submit_classroom_event(self, session_id: str, event_type: str, payload: dict = None, query: str = None) -> dict:
        body = {"eventType": event_type, "payload": payload or {}}
        if query:
            body["query"] = query
        resp = httpx.post(f"{self.base_url}/training/classroom/sessions/{session_id}/events",
                         json=body, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_classroom_session(self, session_id: str) -> dict:
        resp = httpx.get(f"{self.base_url}/training/classroom/sessions/{session_id}",
                        headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
