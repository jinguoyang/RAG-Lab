"""文档入库异步化契约验证脚本。

本脚本只做静态契约检查，避免依赖本地 Redis/Celery 服务即可验证 Web 请求链路
不再同步执行解析、Embedding 和索引写入。
"""

from pathlib import Path
import ast


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"


def _assert(condition: bool, message: str) -> None:
    """用明确失败原因标记文档入库异步化契约缺口。"""
    if not condition:
        raise AssertionError(message)


def _read_backend_file(relative_path: str) -> str:
    """按 UTF-8 读取后端文件，保证中文注释和文档可稳定解析。"""
    return (BACKEND_DIR / relative_path).read_text(encoding="utf-8")


def _function_node(source: str, function_name: str) -> ast.FunctionDef:
    """从 Python 源码中提取指定函数节点，便于检查直接调用关系。"""
    module = ast.parse(source)
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return node
    raise AssertionError(f"缺少函数: {function_name}")


def _calls_function(function: ast.FunctionDef, call_name: str) -> bool:
    """判断函数体内是否直接调用指定函数名。"""
    for node in ast.walk(function):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == call_name:
            return True
    return False


def verify_api_paths_only_enqueue_ingest_jobs() -> None:
    """校验上传、重解析和重试接口对应服务函数不再同步跑本地 Worker。"""
    source = _read_backend_file("app/services/document_service.py")
    for function_name in ("create_document_upload", "reparse_document", "retry_ingest_job"):
        function = _function_node(source, function_name)
        _assert(
            not _calls_function(function, "run_ingest_job"),
            f"{function_name} 仍在请求链路内直接调用 run_ingest_job",
        )
        _assert(
            _calls_function(function, "enqueue_ingest_job"),
            f"{function_name} 未投递后台入库任务",
        )


def verify_worker_contract() -> None:
    """校验 Celery Worker 入口和按 job_id 执行的后台任务存在。"""
    worker_path = BACKEND_DIR / "app/worker.py"
    _assert(worker_path.exists(), "缺少 Celery worker 入口 app/worker.py")
    worker_source = worker_path.read_text(encoding="utf-8")
    _assert("Celery(" in worker_source, "worker.py 未创建 Celery 应用")
    _assert('name="document_ingest.run"' in worker_source, "缺少稳定任务名 document_ingest.run")
    _assert("run_ingest_job_by_id(" in worker_source, "Celery 任务未按 job_id 调用后台入库执行函数")

    service_source = _read_backend_file("app/services/document_service.py")
    _assert("def run_ingest_job_by_id(" in service_source, "缺少按 job_id 重新打开会话的后台执行函数")
    _assert("get_session_factory()" in service_source, "后台执行函数未重新打开数据库 Session")
    _assert("select(users)" in service_source, "后台执行函数未加载作业创建人")


def verify_enqueue_failure_contract() -> None:
    """校验 Celery 投递失败会落库为 failed，并由 API 映射为 503。"""
    service_source = _read_backend_file("app/services/document_service.py")
    routes_source = _read_backend_file("app/api/routes/documents.py")
    _assert("class DocumentIngestEnqueueError" in service_source, "缺少入队失败业务异常")
    _assert("INGEST_ENQUEUE_FAILED" in service_source, "入队失败未写入稳定错误码")
    _assert("stage=\"enqueue\"" in service_source, "入队失败未写入 enqueue 阶段")
    _assert("DocumentIngestEnqueueError" in routes_source, "API 层未捕获入队失败异常")
    _assert("HTTP_503_SERVICE_UNAVAILABLE" in routes_source, "入队失败未映射为 503")


def verify_celery_configuration_contract() -> None:
    """校验 Celery 依赖、配置项和本地启动脚本已补齐。"""
    requirements = _read_backend_file("requirements.txt")
    config_source = _read_backend_file("app/core/config.py")
    env_example = _read_backend_file(".env.example")
    worker_script = BACKEND_DIR / "scripts/start-worker.ps1"
    dev_script = BACKEND_DIR / "scripts/start-dev.ps1"
    load_env_script = BACKEND_DIR / "scripts/load-env.ps1"

    _assert("celery[redis]" in requirements, "requirements.txt 缺少 celery[redis]")
    _assert("prompt-toolkit" in requirements, "requirements.txt 缺少 Celery CLI 所需的 prompt-toolkit")
    _assert("celery_broker_url" in config_source, "配置缺少 celery_broker_url")
    _assert("celery_result_backend" in config_source, "配置缺少 celery_result_backend")
    _assert("CELERY_BROKER_URL" in config_source, "Celery broker 未兼容现有 CELERY_BROKER_URL")
    _assert("RAG_LAB_CELERY_BROKER_URL" in env_example, ".env.example 缺少 Celery broker 示例")
    _assert(worker_script.exists(), "缺少 scripts/start-worker.ps1")
    _assert(load_env_script.exists(), "缺少 scripts/load-env.ps1")
    _assert("SetEnvironmentVariable" in load_env_script.read_text(encoding="utf-8"), "load-env.ps1 未写入进程环境变量")
    _assert("load-env.ps1" in dev_script.read_text(encoding="utf-8"), "start-dev.ps1 未加载 .env")
    worker_script_source = worker_script.read_text(encoding="utf-8")
    _assert("load-env.ps1" in worker_script_source, "start-worker.ps1 未加载 .env")
    _assert("python -m celery" in worker_script_source, "worker 启动脚本应通过 python -m celery 避免 Windows 命令入口缺失")
    _assert("--pool=solo" in worker_script_source, "Windows worker 启动脚本应使用 solo pool")


def main() -> None:
    """执行文档入库异步化契约验收。"""
    verify_api_paths_only_enqueue_ingest_jobs()
    verify_worker_contract()
    verify_enqueue_failure_contract()
    verify_celery_configuration_contract()
    print("Document ingest async contract verification passed.")


if __name__ == "__main__":
    main()
