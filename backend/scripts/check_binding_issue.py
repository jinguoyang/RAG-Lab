"""排查知识库文档绑定问题：删除后重新绑定同名文档导致两个文档都在知识库中。"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_session_factory
from app.tables import document_kb_bindings, documents, document_versions, chunks

KB_ID = "e1edd82d-0d30-454a-b711-5da97857b7d6"
DOC_ID_1 = "8d8cf6a0-8f56-4507-9f2d-eb456d0028d9"  # 被删除的文档
DOC_ID_2 = "7907c6e5-c23c-496a-97e8-60fbed8e2deb"  # 重新绑定的文档
DOC_NAME = "呆滞物料管理办法V1.1.docx"


def main():
    session_factory = get_session_factory()
    with session_factory() as session:
        print("=" * 80)
        print(f"排查知识库文档绑定问题")
        print(f"KB ID: {KB_ID}")
        print(f"文档名称: {DOC_NAME}")
        print("=" * 80)

        # 1. 查询 document_kb_bindings 表中这两个文档的绑定状态
        print("\n【1】查询 document_kb_bindings 表中这两个文档的绑定状态:")
        print("-" * 80)

        bindings = session.execute(
            document_kb_bindings.select().where(
                document_kb_bindings.c.kb_id == KB_ID,
                document_kb_bindings.c.document_id.in_([DOC_ID_1, DOC_ID_2]),
            )
        ).mappings().all()

        if not bindings:
            print("未找到任何绑定记录")
        else:
            for b in bindings:
                print(f"  binding_id: {b['binding_id']}")
                print(f"  document_id: {b['document_id']}")
                print(f"  kb_id: {b['kb_id']}")
                print(f"  version_id: {b['version_id']}")
                print(f"  status: {b['status']}")
                print(f"  chunk_count: {b['chunk_count']}")
                print(f"  created_at: {b['created_at']}")
                print(f"  updated_at: {b['updated_at']}")
                print()

        # 2. 查询 documents 表中 KB 侧文档副本
        print("\n【2】查询 documents 表中 KB 侧文档副本:")
        print("-" * 80)

        kb_docs = session.execute(
            documents.select().where(
                documents.c.kb_id == KB_ID,
                documents.c.name == DOC_NAME,
                documents.c.deleted_at.is_(None),
            )
        ).mappings().all()

        if not kb_docs:
            print("未找到任何未删除的 KB 侧文档副本")
        else:
            for doc in kb_docs:
                print(f"  document_id: {doc['document_id']}")
                print(f"  kb_id: {doc['kb_id']}")
                print(f"  name: {doc['name']}")
                print(f"  source_type: {doc['source_type']}")
                print(f"  status: {doc['status']}")
                print(f"  active_version_id: {doc['active_version_id']}")
                print(f"  metadata: {doc['metadata']}")
                print(f"  created_at: {doc['created_at']}")
                print(f"  deleted_at: {doc['deleted_at']}")
                print()

        # 3. 查询所有已删除的 KB 侧文档副本
        print("\n【3】查询所有已删除的 KB 侧文档副本:")
        print("-" * 80)

        deleted_docs = session.execute(
            documents.select().where(
                documents.c.kb_id == KB_ID,
                documents.c.name == DOC_NAME,
                documents.c.deleted_at.is_not(None),
            )
        ).mappings().all()

        if not deleted_docs:
            print("未找到已删除的 KB 侧文档副本")
        else:
            for doc in deleted_docs:
                print(f"  document_id: {doc['document_id']}")
                print(f"  kb_id: {doc['kb_id']}")
                print(f"  name: {doc['name']}")
                print(f"  status: {doc['status']}")
                print(f"  deleted_at: {doc['deleted_at']}")
                print()

        # 4. 查询该知识库中所有绑定（不限文档ID）
        print("\n【4】查询该知识库中所有活跃绑定:")
        print("-" * 80)

        all_bindings = session.execute(
            document_kb_bindings.select().where(
                document_kb_bindings.c.kb_id == KB_ID,
                document_kb_bindings.c.status.in_(["active", "processing", "pending"]),
            )
        ).mappings().all()

        if not all_bindings:
            print("未找到任何活跃绑定")
        else:
            for b in all_bindings:
                # 获取文档名称
                doc = session.execute(
                    documents.select().where(
                        documents.c.document_id == b['document_id'],
                    )
                ).mappings().first()

                doc_name = doc['name'] if doc else "未知"
                print(f"  binding_id: {b['binding_id']}")
                print(f"  document_id: {b['document_id']}")
                print(f"  document_name: {doc_name}")
                print(f"  status: {b['status']}")
                print()

        # 5. 查询 KB 侧文档副本中同名文档
        print("\n【5】查询 KB 侧文档副本中所有名为 '{}' 的文档（包括已删除）:".format(DOC_NAME))
        print("-" * 80)

        all_same_name = session.execute(
            documents.select().where(
                documents.c.kb_id == KB_ID,
                documents.c.name == DOC_NAME,
            )
        ).mappings().all()

        if not all_same_name:
            print("未找到任何同名文档")
        else:
            for doc in all_same_name:
                print(f"  document_id: {doc['document_id']}")
                print(f"  status: {doc['status']}")
                print(f"  deleted_at: {doc['deleted_at']}")
                print(f"  created_at: {doc['created_at']}")
                print()


if __name__ == "__main__":
    main()
