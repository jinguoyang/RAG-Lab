"""B-318: 文档解析 Provider 路由 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.schemas.auth import CurrentUserResponse
from app.services.parser_routing import get_routing_strategy_info, list_parser_capabilities

router = APIRouter(prefix="/parser-routing", tags=["parser-routing"])


@router.get("/strategies")
def read_routing_strategies(
    current_user: CurrentUserResponse = Depends(get_current_user),
) -> dict:
    """返回所有可用的解析路由策略和 Provider 信息。"""
    _ = current_user
    return get_routing_strategy_info()


@router.get("/providers")
def read_parser_providers(
    current_user: CurrentUserResponse = Depends(get_current_user),
) -> list[dict]:
    """返回所有已注册的解析器 Provider 能力。"""
    _ = current_user
    capabilities = list_parser_capabilities()
    return [
        {
            "name": cap.parser_name,
            "supportedTypes": list(cap.supported_types),
            "supportsBbox": cap.supports_bbox,
            "supportsTable": cap.supports_table,
            "supportsOcr": cap.supports_ocr,
            "supportsLayout": cap.supports_layout,
            "confidence": cap.confidence,
            "costLevel": cap.cost_level,
            "version": cap.version,
        }
        for cap in capabilities
    ]
