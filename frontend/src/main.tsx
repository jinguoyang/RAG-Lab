import React from "react";
import ReactDOM from "react-dom/client";
import App from "./app/App";
import "./styles/index.css";

/**
 * 应用入口。
 * 负责挂载 React 根节点并加载全局样式。
 */
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
