# RAG-Lab 前端工程

## 工程定位

`frontend/` 是 RAG-Lab 当前阶段的正式前端开发入口。

本工程从 `screanshot/prototype/` 复制而来，保留原型页面和设计系统作为开发起点；原 prototype 目录继续作为设计原型归档，不直接承载正式开发。

选择复制而不是从 0 搭建的原因：

- 原型已经具备 Vite、React、TypeScript、路由、样式和页面结构。
- 原型页面与设计稿编号一一对应，复制后能保留页面资产。
- 正式工程和原型归档分离，后续开发不会污染设计原型。

## 本地运行

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm install
npm run dev
```

## 构建检查

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

## 最小验证

当前前端工程只定义了 `dev` 和 `build` 脚本。提交前至少运行：

```powershell
cd C:\Users\Public\Documents\Code\jin\rag-lab\frontend
npm run build
```

验证通过标准：

- Vite 构建成功。
- 没有 TypeScript 或打包错误。
- 生成的 `dist/` 不提交到 Git。

## 开发约定

- 页面入口从 `src/main.tsx` 挂载到 `src/app/App.tsx`。
- 路由集中维护在 `src/app/routes.tsx`。
- 业务页面放在 `src/app/pages/`。
- RAG-Lab 自有组件优先放在 `src/app/components/rag/`。
- shadcn / Radix 基础组件保留在 `src/app/components/ui/`。
- 全局样式和设计 token 维护在 `src/styles/`。

正式接入接口时，应新增 service、adapter 和 type 分层，避免页面组件直接拼接 API 路径或依赖后端 DTO。
