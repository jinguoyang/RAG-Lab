"""培训报表与薄弱点统计端点。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.schemas.auth import CurrentUserResponse
from app.schemas.training_report import TrainingReportDTO
from app.services.training_report_service import get_training_report

router = APIRouter(prefix="/training/reports", tags=["training"])


@router.get("/summary", response_model=TrainingReportDTO)
def get_training_report_summary(
    app_id: str = Query(..., alias="appId"),
    current_user: Annotated[CurrentUserResponse, Depends(get_current_user)] = None,
    session: Session = Depends(get_db_session),
) -> TrainingReportDTO:
    """培训完成率、平均分、错题分布和薄弱能力统计。"""
    try:
        return get_training_report(session, app_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误") from exc
