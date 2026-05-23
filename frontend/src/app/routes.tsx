import { createBrowserRouter } from "react-router";
import type { ComponentType } from "react";
import { PlatformLayout } from "./layouts/PlatformLayout";
import { KBLayout } from "./layouts/KBLayout";

function PageLoading() {
  return (
    <div className="flex h-full min-h-40 items-center justify-center text-sm text-stone-gray">
      加载中...
    </div>
  );
}

function lazyPage<T extends Record<string, unknown>>(loader: () => Promise<T>, exportName: keyof T) {
  return async () => ({
    Component: (await loader())[exportName] as ComponentType,
    HydrateFallback: PageLoading,
  });
}

export const router = createBrowserRouter([
  { path: "/login", lazy: lazyPage(() => import("./pages/P01_Login"), "Login") },
  { path: "/embed/runtime", lazy: lazyPage(() => import("./pages/P20_EmbeddedRuntime"), "EmbeddedRuntime") },
  {
    path: "/",
    Component: PlatformLayout,
    HydrateFallback: PageLoading,
    children: [
      { index: true, lazy: lazyPage(() => import("./pages/P02_PlatformHome"), "PlatformHome") },
      { path: "users", lazy: lazyPage(() => import("./pages/P03_UserManagement"), "UserManagement") },
      { path: "groups", lazy: lazyPage(() => import("./pages/P04_UserGroupManagement"), "UserGroupManagement") },
      { path: "rag-apps", lazy: lazyPage(() => import("./pages/P13_RagAppManagement"), "RagAppManagement") },
      { path: "dictionaries", lazy: lazyPage(() => import("./pages/P14_DictionaryManagement"), "DictionaryManagement") },
      { path: "library", lazy: lazyPage(() => import("./pages/P17_LibraryManagement"), "LibraryManagement") },
      { path: "library/:libraryId", lazy: lazyPage(() => import("./pages/P18_LibraryDocuments"), "LibraryDocuments") },
      { path: "library/:libraryId/documents/:docId", lazy: lazyPage(() => import("./pages/P16_LibraryDetail"), "LibraryDetail") },
      { path: "library/:libraryId/members", lazy: lazyPage(() => import("./pages/P19_LibraryMembers"), "LibraryMembers") },
    ],
  },
  {
    path: "/kb/:kbId",
    Component: KBLayout,
    HydrateFallback: PageLoading,
    children: [
      { index: true, lazy: lazyPage(() => import("./pages/P05_KBOverview"), "KBOverview") },
      { path: "docs", lazy: lazyPage(() => import("./pages/P06_DocumentCenter"), "DocumentCenter") },
      { path: "docs/:docId", lazy: lazyPage(() => import("./pages/P07_DocumentDetail"), "DocumentDetail") },
      { path: "config", lazy: lazyPage(() => import("./pages/P08_ConfigCenter"), "ConfigCenter") },
      { path: "qa", lazy: lazyPage(() => import("./pages/P09_QADebug"), "QADebug") },
      { path: "history", lazy: lazyPage(() => import("./pages/P10_QAHistory"), "QAHistory") },
      { path: "graph", lazy: lazyPage(() => import("./pages/P11_GraphSearchAnalysis"), "GraphSearchAnalysis") },
      { path: "members", lazy: lazyPage(() => import("./pages/P12_MembersAndPermissions"), "MembersAndPermissions") },
    ],
  },
]);
