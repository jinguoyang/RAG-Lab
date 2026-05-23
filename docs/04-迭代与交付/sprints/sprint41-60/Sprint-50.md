# 迭代计划 Sprint 50

## 1. Sprint 基本信息

- Sprint 名称：Sprint 50
- Sprint 主题：场景化智能应用验收硬化与文档同步
- 涉及 Epic：E32 场景化智能应用
- 建议版本：V2.1
- 时间范围：待排期
- 目标：补齐培训报告、端到端验收、权限回归、接口文档和发布说明，让两个典型场景可作为演示和后续开发基线。

## 2. 关键假设

- Sprint 47 至 Sprint 49 已完成两个场景的主要功能。
- 本 Sprint 不继续新增第三个业务场景。
- 文档状态只更新唯一状态源，历史 Sprint 文档作为归档记录。

## 3. 计划事项

| Backlog | 标题 | 优先级 | 预估 | 状态 |
| --- | --- | --- | --- | --- |
| B-255 | 新增应用级培训报告接口和 P13 摘要展示 | P1 | 1.5d | Ready |
| B-256 | 建立两个场景的端到端验收脚本 | P0 | 2d | Ready |
| B-257 | 补齐权限、Embed Token 和 Runtime 安全回归 | P0 | 1.5d | Ready |
| B-258 | 同步系统设计、接口设计、数据模型、OpenAPI 和发布说明 | P1 | 2d | Ready |

## 4. 验收标准

- 知识库问答助手端到端验收通过：创建、API 调用、嵌入页、Citation、反馈、QARun 回溯。
- 员工培训助手端到端验收通过：创建、讲解、测验、评分、错题解释、训练结果追溯。
- Embed Token 过期、篡改、跨 App 使用均被拒绝。
- 知识库 disabled 后，两类助手 Runtime 调用均返回稳定错误。
- 文档、OpenAPI 和产品待办状态与实际实现一致。

## 5. 范围边界

- 不新增第三个场景模板。
- 不扩展多租户 SaaS 或公网匿名访问能力。
- 不把 local/mock 验证描述为真实 Provider 网络级通过。

## 6. 验证命令

```powershell
cd backend
conda run -n rag-lab python -m compileall app
conda run -n rag-lab pytest app/tests/unit -q
conda run -n rag-lab pytest app/tests/integration -q
conda run -n rag-lab python scripts/export_openapi.py
```

```powershell
cd frontend
npm run lint
npm run test
npm run build
npx playwright test
```

```powershell
git diff --check
```

## 7. 关联文档

- [场景化智能应用开发计划](../../plans/2026-05-24-agent-scenario-apps.md)
