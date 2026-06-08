"""使用真实知识库文档生成课程蓝图并输出教学质量评估。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import get_session_factory
from app.schemas.training_plan import DocumentDTO
from app.services.training_plan_service import _generate_sections_with_llm
from app.tables import chunks, documents, rag_apps


def _parse_args() -> argparse.Namespace:
    """解析真实课程质量评估参数。"""
    parser = argparse.ArgumentParser(description="生成章节级课程蓝图并检查 0.7 初版质量门槛。")
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--job-title", default="仓库及物料管理相关岗位")
    parser.add_argument(
        "--job-description",
        default="需要识别呆滞物料、组织评审、协同处置并完成账务和改进闭环。",
    )
    parser.add_argument("--threshold", type=float, default=0.7)
    return parser.parse_args()


def main() -> int:
    """读取整篇文档、调用课程蓝图生成并打印逐节评估结果。"""
    args = _parse_args()
    with get_session_factory()() as session:
        rows = session.execute(
            select(
                chunks.c.chunk_id,
                chunks.c.document_id,
                documents.c.name.label("document_name"),
                chunks.c.kb_id,
                chunks.c.chunk_index,
                chunks.c.section,
                chunks.c.heading,
                chunks.c.content,
                chunks.c.metadata,
            )
            .select_from(chunks.outerjoin(documents, chunks.c.document_id == documents.c.document_id))
            .where(chunks.c.document_id == args.document_id, chunks.c.status == "active")
            .order_by(chunks.c.chunk_index.asc())
        ).mappings().all()
        if not rows:
            raise SystemExit("指定文档没有有效 Chunk。")

        app_id = session.execute(
            select(rag_apps.c.app_id)
            .where(rag_apps.c.kb_id == rows[0]["kb_id"], rag_apps.c.status == "active")
            .limit(1)
        ).scalar_one_or_none()
        if app_id is None:
            raise SystemExit("文档所在知识库没有可用的员工培训 App。")

        title = str(rows[0]["document_name"] or args.document_id)
        sections = _generate_sections_with_llm(
            session,
            args.job_title,
            args.job_description,
            [DocumentDTO(documentId=args.document_id, title=title, abilityGroup="岗位课程")],
            rows,
            str(app_id),
        )
        if not sections:
            raise SystemExit("课程蓝图生成失败。")

        average_score = round(sum(item.teachingQualityScore for item in sections) / len(sections), 3)
        result = {
            "documentId": args.document_id,
            "sectionCount": len(sections),
            "averageScore": average_score,
            "threshold": args.threshold,
            "passed": average_score >= args.threshold
            and all(item.teachingQualityScore >= args.threshold for item in sections),
            "sections": [
                {
                    "sectionId": item.sectionId,
                    "title": item.title,
                    "score": item.teachingQualityScore,
                    "evidenceCount": len(item.evidenceChunkIds),
                    "learningObjective": item.learningObjective,
                    "teachingScript": item.teachingScript.model_dump() if item.teachingScript else None,
                }
                for item in sections
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
