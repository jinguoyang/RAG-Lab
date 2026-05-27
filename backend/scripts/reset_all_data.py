"""清除 RAG-Lab 项目全部数据，相当于彻底初始化。

使用方式：
    cd backend
    python scripts/reset_all_data.py          # 交互式确认
    python scripts/reset_all_data.py --yes    # 跳过确认（CI / 脚本调用）
    python scripts/reset_all_data.py --dry-run # 仅打印将要执行的操作，不实际执行

读取 .env 中的连接配置，依次清空：
    1. PostgreSQL  — DROP + CREATE DATABASE（rag-lab，可选 rag-trainning）
    2. Milvus      — DROP COLLECTION
    3. OpenSearch   — DELETE INDEX
    4. MinIO        — 删除 bucket 内全部对象
    5. Neo4j        — 删除全部节点和关系
    6. Redis        — FLUSHDB（broker DB + result DB）
"""

import argparse
import os
import sys
import urllib.parse
from pathlib import Path

# ---------------------------------------------------------------------------
# 加载 .env
# ---------------------------------------------------------------------------

def _load_dotenv(path: Path) -> dict[str, str]:
    """简易 .env 解析，不依赖 python-dotenv。"""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        env[key] = value
    return env


def _get(env: dict[str, str], *keys: str, default: str = "") -> str:
    """按优先级依次尝试多个 key，返回第一个非空值。"""
    for k in keys:
        v = env.get(k, "").strip()
        if v:
            return v
    return default


# ---------------------------------------------------------------------------
# 各组件清理函数
# ---------------------------------------------------------------------------

def reset_postgresql(env: dict[str, str], dry_run: bool) -> None:
    """连接 postgres 维护库，DROP + CREATE rag-lab（和 rag-trainning）。"""
    import psycopg

    db_url = _get(env, "RAG_LAB_DATABASE_URL", "DATABASE_URL")
    if not db_url:
        print("  [跳过] 未配置 DATABASE_URL")
        return

    # 从 URL 中提取 dbname
    parsed = urllib.parse.urlparse(db_url)
    target_db = parsed.path.lstrip("/")
    # 构造连接到 postgres 维护库的 URL
    admin_url = db_url.rsplit("/", 1)[0] + "/postgres"

    training_db = _get(env, "RAG_LAB_TRAINING_DATABASE_URL", "EXT_TRAINING_DATABASE_URL")
    training_dbname = ""
    if training_db:
        training_parsed = urllib.parse.urlparse(training_db)
        training_dbname = training_parsed.path.lstrip("/")

    print(f"  PostgreSQL 目标库: {target_db}", end="")
    if training_dbname:
        print(f", {training_dbname}", end="")
    print()

    if dry_run:
        return

    # autocommit 模式，因为 DROP/CREATE DATABASE 不能在事务中执行
    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for dbname in [target_db, training_dbname]:
                if not dbname:
                    continue
                # 终止目标库上的所有连接
                cur.execute(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
                    (dbname,),
                )
                cur.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
                print(f"    DROP DATABASE IF EXISTS {dbname}")
                cur.execute(f'CREATE DATABASE "{dbname}"')
                print(f"    CREATE DATABASE {dbname}")


def reset_milvus(env: dict[str, str], dry_run: bool) -> None:
    from pymilvus import MilvusClient

    uri = _get(env, "RAG_LAB_MILVUS_URI", "MILVUS_URI")
    token = _get(env, "RAG_LAB_MILVUS_TOKEN", "MILVUS_TOKEN") or None
    collection = _get(env, "RAG_LAB_MILVUS_COLLECTION", "MILVUS_COLLECTION", default="rag_chunk_embeddings")

    if not uri:
        print("  [跳过] 未配置 MILVUS_URI")
        return

    print(f"  Milvus collection: {collection}")

    if dry_run:
        return

    client = MilvusClient(uri=uri, token=token)
    if client.has_collection(collection):
        client.drop_collection(collection)
        print(f"    DROPPED collection {collection}")
    else:
        print(f"    collection {collection} 不存在，无需清理")
    client.close()


def reset_opensearch(env: dict[str, str], dry_run: bool) -> None:
    from opensearchpy import OpenSearch

    hosts_str = _get(env, "RAG_LAB_OPENSEARCH_HOSTS", "OPENSEARCH_HOSTS")
    username = _get(env, "RAG_LAB_OPENSEARCH_USERNAME", "OPENSEARCH_USERNAME") or None
    password = _get(env, "RAG_LAB_OPENSEARCH_PASSWORD", "OPENSEARCH_PASSWORD") or None
    index = _get(env, "RAG_LAB_OPENSEARCH_INDEX", "OPENSEARCH_INDEX", default="rag_chunks")

    if not hosts_str:
        print("  [跳过] 未配置 OPENSEARCH_HOSTS")
        return

    print(f"  OpenSearch index: {index}")

    if dry_run:
        return

    parsed = urllib.parse.urlparse(hosts_str)
    host_config = {
        "hosts": [hosts_str],
        "use_ssl": parsed.scheme == "https",
        "verify_certs": False,
    }
    if username and password:
        host_config["http_auth"] = (username, password)

    client = OpenSearch(**host_config)
    if client.indices.exists(index=index):
        client.indices.delete(index=index)
        print(f"    DELETED index {index}")
    else:
        print(f"    index {index} 不存在，无需清理")
    client.close()


def reset_minio(env: dict[str, str], dry_run: bool) -> None:
    from minio import Minio

    endpoint = _get(env, "RAG_LAB_MINIO_ENDPOINT", "MINIO_ENDPOINT")
    access_key = _get(env, "RAG_LAB_MINIO_ACCESS_KEY", "MINIO_ACCESS_KEY", default="minioadmin")
    secret_key = _get(env, "RAG_LAB_MINIO_SECRET_KEY", "MINIO_SECRET_KEY", default="minioadmin")
    secure = _get(env, "RAG_LAB_MINIO_SECURE", "MINIO_SECURE", default="false").lower() == "true"
    bucket = _get(env, "RAG_LAB_STORAGE_BUCKET", "STORAGE_BUCKET", "MINIO_BUCKET", default="rag-lab-source")

    if not endpoint:
        print("  [跳过] 未配置 MINIO_ENDPOINT")
        return

    print(f"  MinIO bucket: {bucket}")

    if dry_run:
        return

    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
    if client.bucket_exists(bucket):
        objects = list(client.list_objects(bucket, recursive=True))
        count = 0
        for obj in objects:
            client.remove_object(bucket, obj.object_name)
            count += 1
        print(f"    删除了 {count} 个对象")
        # 删除空 bucket
        client.remove_bucket(bucket)
        print(f"    REMOVED bucket {bucket}")
        # 重建空 bucket
        client.make_bucket(bucket)
        print(f"    RE-CREATED bucket {bucket}")
    else:
        print(f"    bucket {bucket} 不存在，创建空 bucket")
        client.make_bucket(bucket)
        print(f"    CREATED bucket {bucket}")


def reset_neo4j(env: dict[str, str], dry_run: bool) -> None:
    from neo4j import GraphDatabase

    uri = _get(env, "RAG_LAB_NEO4J_URI", "NEO4J_URI")
    username = _get(env, "RAG_LAB_NEO4J_USERNAME", "NEO4J_USERNAME", default="neo4j")
    password = _get(env, "RAG_LAB_NEO4J_PASSWORD", "NEO4J_PASSWORD")
    database = _get(env, "RAG_LAB_NEO4J_DATABASE", "NEO4J_DATABASE", default="neo4j")

    if not uri:
        print("  [跳过] 未配置 NEO4J_URI")
        return

    print(f"  Neo4j database: {database}")

    if dry_run:
        return

    driver = GraphDatabase.driver(uri, auth=(username, password))
    with driver.session(database=database) as session:
        # 先删关系，再删节点
        result = session.run("MATCH ()-[r]->() DELETE r")
        summary = result.consume()
        rel_count = summary.counters.relationships_deleted
        print(f"    删除了 {rel_count} 条关系")

        result = session.run("MATCH (n) DELETE n")
        summary = result.consume()
        node_count = summary.counters.nodes_deleted
        print(f"    删除了 {node_count} 个节点")

    driver.close()


def reset_redis(env: dict[str, str], dry_run: bool) -> None:
    import redis

    broker_url = _get(env, "RAG_LAB_CELERY_BROKER_URL", "CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
    result_url = _get(env, "RAG_LAB_CELERY_RESULT_BACKEND", "CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/1")

    print(f"  Redis broker DB: {_extract_redis_db(broker_url)}")
    print(f"  Redis result DB: {_extract_redis_db(result_url)}")

    if dry_run:
        return

    for url in [broker_url, result_url]:
        client = redis.Redis.from_url(url)
        db = client.connection_pool.connection_kwargs.get("db", "?")
        count = 0
        for key in client.scan_iter("*"):
            client.delete(key)
            count += 1
        print(f"    FLUSHDB db={db}，删除了 {count} 个 key")
        client.close()


def _extract_redis_db(url: str) -> int | str:
    """从 redis URL 中提取 db 编号。"""
    import urllib.parse as up
    parsed = up.urlparse(url)
    path = parsed.path.lstrip("/")
    return int(path) if path.isdigit() else path or 0


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

STEPS = [
    ("PostgreSQL", reset_postgresql),
    ("Milvus", reset_milvus),
    ("OpenSearch", reset_opensearch),
    ("MinIO", reset_minio),
    ("Neo4j", reset_neo4j),
    ("Redis", reset_redis),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="清空 RAG-Lab 全部数据")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认提示")
    parser.add_argument("--dry-run", action="store_true", help="仅打印操作，不实际执行")
    args = parser.parse_args()

    # 定位 .env
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent
    env_path = backend_dir / ".env"

    if not env_path.exists():
        print(f"错误：找不到 .env 文件: {env_path}")
        sys.exit(1)

    env = _load_dotenv(env_path)
    print(f"已加载配置: {env_path}\n")

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"模式: {mode}")
    print("即将清空以下组件的数据:\n")
    for name, _ in STEPS:
        print(f"  - {name}")
    print()

    if args.dry_run:
        print("--- dry-run 开始 ---\n")

    if not args.yes and not args.dry_run:
        confirm = input("确认清空全部数据？输入 YES 继续: ")
        if confirm.strip() != "YES":
            print("已取消。")
            sys.exit(0)
        print()

    errors: list[str] = []
    for name, fn in STEPS:
        print(f"[{name}]")
        try:
            fn(env, args.dry_run)
        except Exception as exc:
            print(f"    [ERROR] {exc}")
            errors.append(f"{name}: {exc}")
        print()

    if args.dry_run:
        print("--- dry-run 结束 ---")
    elif errors:
        print(f"完成，但有 {len(errors)} 个错误:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("全部清空完成。")


if __name__ == "__main__":
    main()
