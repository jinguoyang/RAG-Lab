import { createBrowserRouter } from "react-router";
import { BindingPage } from "./pages/BindingPage";
import { ReviewPage } from "./pages/ReviewPage";

export const router = createBrowserRouter([
  { path: "/", element: <ReviewPage /> },
  { path: "/bindings", element: <BindingPage /> },
  { path: "/reviews", element: <ReviewPage /> },
]);
