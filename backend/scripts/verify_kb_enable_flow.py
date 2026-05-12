"""校验停用知识库可以通过明确操作恢复启用。"""

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"


def _assert(condition: bool, message: str) -> None:
    """提供清晰失败信息，便于定位启用流程缺失位置。"""
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    """按 UTF-8 读取源码，避免中文文案在 Windows 下乱码。"""
    return path.read_text(encoding="utf-8")


def verify_backend_enable_contract() -> None:
    """校验后端具备知识库启用服务函数、路由和审计动作。"""
    service = _read(BACKEND_DIR / "app/services/knowledge_base_service.py")
    route = _read(BACKEND_DIR / "app/api/routes/knowledge_bases.py")

    _assert("def enable_knowledge_base(" in service, "服务层缺少 enable_knowledge_base")
    _assert('status="active"' in service, "启用操作未将知识库状态恢复为 active")
    _assert("knowledge_base.enable" in service, "启用操作缺少审计动作")
    _assert("@router.post(\"/{kb_id}/enable\"" in route, "路由层缺少启用知识库接口")
    _assert("enable_knowledge_base_endpoint" in route, "路由层缺少启用 endpoint")
    _assert("enable_knowledge_base(session, current_user, kb_id)" in route, "启用 endpoint 未调用服务层")


def verify_frontend_enable_contract() -> None:
    """校验前端 P02 在 disabled 知识库上展示启用操作。"""
    service = _read(FRONTEND_DIR / "src/app/services/knowledgeBaseService.ts")
    page = _read(FRONTEND_DIR / "src/app/pages/P02_PlatformHome.tsx")

    _assert("enableKnowledgeBase" in service, "前端服务层缺少 enableKnowledgeBase")
    _assert("/enable" in service, "前端启用请求未调用 enable 接口")
    _assert("handleEnable" in page, "P02 缺少启用处理函数")
    _assert("恢复启用" in page, "P02 缺少恢复启用按钮或文案")
    _assert("enableKnowledgeBase" in page, "P02 未调用前端启用服务")


def main() -> None:
    """执行知识库启用流程源码级验收。"""
    verify_backend_enable_contract()
    verify_frontend_enable_contract()
    print("Knowledge base enable flow verification passed.")


if __name__ == "__main__":
    main()
