# 外部培训应用 Stub 替换设计

## 背景

外部培训应用从平台拆分后，多个服务函数仍是模板 stub，需接入平台 RAG API 替换为真实实现。

## 当前状态

| 函数 | 文件 | 现状 |
|---|---|---|
| `_generate_template_plan()` | `training_plan_service.py:154` | 硬编码模板 |
| `_generate_template_questions()` | `training_question_service.py:125` | 硬编码 4 道题 |
| `_generate_classroom_answer()` | `training_classroom_service.py:414` | 状态判断 + 模板字符串 |
| `_is_query_relevant()` | `training_classroom_service.py:309` | 始终返回 True |
| `_extract_ui_actions()` | `training_classroom_service.py:444` | 返回空列表 |
| `PlatformClient` | `platform_client.py` | 只有 `__init__`，无方法 |

## 并行开发 Track 划分

### 用户当前工作（已进行中）

- **平台侧**：新建 `/training/plans/drafts` 端点（RAG 检索 + LLM 生成学习计划）
- **外部应用侧**：`PlatformClient.create_plan_draft()` + 替换 `_generate_template_plan()`
- **改动文件**：
  - 平台：`backend/app/api/routes/training_plans.py`（新建）、相关 service
  - 外部：`platform_client.py`（加方法）、`training_plan_service.py`（替换函数体）

### Track A — 题目生成接入

- **平台侧**：新建 `/training/questions/drafts` 端点
- **外部应用侧**：`PlatformClient.create_question_drafts()` + 替换 `_generate_template_questions()`
- **改动文件**：
  - 平台：`backend/app/api/routes/training_questions.py`（新建）
  - 外部：`platform_client.py`（加方法）、`training_question_service.py`（替换函数体）
- **与用户工作无文件冲突**

### Track B — 课堂 RAG 回答

- **外部应用侧**：`PlatformClient.chat()` 调平台 `app-runtime/chat-messages` + 替换 `_generate_classroom_answer()`
- **改动文件**：`platform_client.py`（加方法）、`training_classroom_service.py`（替换 `_generate_classroom_answer` 函数体）
- **依赖**：`PlatformClient` 基础结构存在（用户合完 plans/drafts 后即有）

### Track C — 偏题检测 + UI 动作

- **外部应用侧**：实现 `_is_query_relevant()` + `_extract_ui_actions()`
- **改动文件**：`training_classroom_service.py`（改 `:309` 和 `:444` 两处）
- **可与 Track B 并行**（不同函数，不冲突）

## 合并策略

- `platform_client.py`：三个 track 各加不同方法，后合者 rebase
- `training_classroom_service.py`：Track B 改 `_generate_classroom_answer`（:414），Track C 改 `_is_query_relevant`（:309）和 `_extract_ui_actions`（:444），行距大不冲突
- 平台侧新建文件各自独立，无冲突

## 依赖关系

```
用户工作（plans/drafts）
    └── Track A（questions/drafts）—— 完全独立，可并行
    └── Track B（classroom RAG）—— 依赖 PlatformClient 基础结构
         └── Track C（偏题 + UI 动作）—— 与 B 并行，不同函数
```
