import { createBrowserRouter } from "react-router";
import { PlatformLayout } from "./layouts/PlatformLayout";
import { KBLayout } from "./layouts/KBLayout";

import { Login } from "./pages/P01_Login";
import { PlatformHome } from "./pages/P02_PlatformHome";
import { UserManagement } from "./pages/P03_UserManagement";
import { UserGroupManagement } from "./pages/P04_UserGroupManagement";
import { KBOverview } from "./pages/P05_KBOverview";
import { DocumentCenter } from "./pages/P06_DocumentCenter";
import { DocumentDetail } from "./pages/P07_DocumentDetail";
import { ConfigCenter } from "./pages/P08_ConfigCenter";
import { QADebug } from "./pages/P09_QADebug";
import { QAHistory } from "./pages/P10_QAHistory";
import { GraphSearchAnalysis } from "./pages/P11_GraphSearchAnalysis";
import { MembersAndPermissions } from "./pages/P12_MembersAndPermissions";

export const router = createBrowserRouter([
  { path: "/login", Component: Login },
  {
    path: "/",
    Component: PlatformLayout,
    children: [
      { index: true, Component: PlatformHome },
      { path: "users", Component: UserManagement },
      { path: "groups", Component: UserGroupManagement },
    ],
  },
  {
    path: "/kb/:kbId",
    Component: KBLayout,
    children: [
      { index: true, Component: KBOverview },
      { path: "docs", Component: DocumentCenter },
      { path: "docs/:docId", Component: DocumentDetail },
      { path: "config", Component: ConfigCenter },
      { path: "qa", Component: QADebug },
      { path: "history", Component: QAHistory },
      { path: "graph", Component: GraphSearchAnalysis },
      { path: "members", Component: MembersAndPermissions },
    ],
  },
]);
