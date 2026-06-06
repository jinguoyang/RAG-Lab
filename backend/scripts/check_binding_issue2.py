"""进一步排查：查看文档库文档 495bc429 的详细信息。"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_session_factory
from app.tables import document_kb_bindings, documents, document_versions

KB_ID = "e1edd82d-0d30-454a-b711-5da97857b7d6"


def main():
    session_factory = get_session_factory()
    with session_factory() as session:
        print("=" * 80)
        print("查看文档库文档 495bc429-a245-4f9f-8109-beac6ef7f3b6 的详细信息")
        print("=" * 80)

        # 查询文档库文档
        lib_doc = session.execute(
            documents.select().where(
                documents.c.document_id == "495bc429-a245-4f9f-8109-beac6ef7f3b6",
            )
        ).mappings().first()

        if lib_doc:
            print("\n【文档库文档 495bc429】:")
            print(f"  document_id: {lib_doc['document_id']}")
            print(f"  name: {lib_doc['name']}")
            print(f"  kb_id: {lib_doc['kb_id']}")
            print(f"  library_id: {lib_doc['library_id']}")
            print(f"  source_type: {lib_doc['source_type']}")
            print(f"  status: {lib_doc['status']}")
            print(f"  active_version_id: {lib_doc['active_version_id']}")
            print(f"  metadata: {lib_doc['metadata']}")
            print(f"  deleted_at: {lib_doc['deleted_at']}")

        # 查询该文档的版本
        print("\n【文档库文档 495bc429 的版本】:")
        versions = session.execute(
            document_versions.select().where(
                document_versions.c.document_id == "495bc429-a245-4f9f-8109-beac6ef7f3b6",
            )
        ).mappings().all()

        for v in versions:
            print(f"  version_id: {v['version_id']}")
            print(f"  version_no: {v['version_no']}")
            print(f"  parse_status: {v['parse_status']}")
            print(f"  deleted_at: {v['deleted_at']}")
            print()

        # 查询绑定 5cbdad4b 的详细信息
        print("\n【绑定 5cbdad4b 的详细信息】:")
        binding = session.execute(
            document_kb_bindings.select().where(
                document_kb_bindings.c.binding_id == "5cbdad4b-0fc0-4f49-beeb-1359b81067e8",
            )
        ).mappings().first()

        if binding:
            print(f"  binding_id: {binding['binding_id']}")
            print(f"  document_id: {binding['document_id']}")
            print(f"  kb_id: {binding['kb_id']}")
            print(f"  version_id: {binding['version_id']}")
            print(f"  status: {binding['status']}")
            print(f"  active_chunk_revision_id: {binding['active_chunk_revision_id']}")
            print(f"  created_at: {binding['created_at']}")

            # 查找 KB 侧文档
            kb_doc = session.execute(
                documents.select().where(
                    documents.c.document_id == (
                        session.execute(
                            document_versions.select().where(
                                document_versions.c.version_id == binding['version_id'],
                            ).limit(1)
                        ).mappings().first() or {}
                    ).get('document_id', '00000000-0000-0000-0000-000000000000'),
                )
            ).mappings().first()

            if kb_doc:
                print("\n  【对应的 KB 侧文档】:")
                print(f"    document_id: {kb_doc['document_id']}")
                print(f"    name: {kb_doc['name']}")
                print(f"    status: {kb_doc['status']}")
                print(f"    metadata: {kb_doc['metadata']}")

        # 汇总
        print("\n" + "=" * 80)
        print("【问题汇总】")
        print("=" * 80)
        print("""
根据查询结果，发现存在两个同名文档库文档都被绑定到了知识库：

1. 文档库文档 8d8cf6a0 (呆滞物料管理办法V1.1.docx)
   - 绑定 ID: afd4b333
   - 绑定状态: active
   - KB 侧文档: 7907c6e5

2. 文档库文档 495bc429 (呆滞物料管理办法V1.1.docx)
   - 绑定 ID: 5cbdad4b
   - 绑定状态: active

这两个是不同的文档库文档（不同的 document_id），只是名字相同。
系统允许绑定不同文档库文档到同一个知识库，即使名字相同。

用户可能的操作：
- 以为删除了 8d8cf6a0，但实际上绑定仍然存在
- 或者删除的是之前的某个版本（739e874c 已删除）
- 然后又绑定了 495bc429

这就是为什么知识库中出现了两个同名文档。
""")


if __name__ == "__main__":
    main()
