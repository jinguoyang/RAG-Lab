"""培训报表与薄弱点统计端点。"""
from typing import Annotated

from fastapi import APIRouter, Header, Query
from sqlalchemy.orm import Session

from fastapi import Depends
from app.api.routes.app_runtime import _extract_bearer_token, _raise_runtime_error
from app.core.database import get_db_session
from app.schemas.training_report import TrainingReportDTO
from app.services.training_report_service import get_training_report

router = APIRouter(prefix="/training/reports", tags=["training"])


@router.get("/summary", response_model=TrainingReportDTO)
def get_training_report_summary(
    app_id: str = Query(..., alias="appId"),
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: Session = Depends(get_db_session),
) -> TrainingReportDTO:
    """培训完成率、平均分、错题分布和薄弱能力统计。"""
    _extract_bearer_token(authorization)
    try:
        return get_training_report(session, app_id)
    except Exception as exc:
        _raise_runtime_error(exc)
        raise
