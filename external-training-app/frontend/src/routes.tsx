import { createBrowserRouter } from "react-router";
import { AppLayout } from "./components/AppLayout";
import { ReviewPage } from "./pages/ReviewPage";
import { ClassroomPage } from "./pages/ClassroomPage";
import { HomePage } from "./pages/HomePage";
import { QuestionReviewPage } from "./pages/QuestionReviewPage";
import { QuestionBankPage } from "./pages/QuestionBankPage";
import { PlanDetailPage } from "./pages/PlanDetailPage";
import { QuizPage } from "./pages/QuizPage";
import { TaskDetailPage } from "./pages/TaskDetailPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "reviews", element: <ReviewPage /> },
      { path: "plans/:planId", element: <PlanDetailPage /> },
      { path: "plans/:planId/classroom", element: <ClassroomPage /> },
      { path: "plans/:planId/quiz", element: <QuizPage /> },
      { path: "questions", element: <QuestionReviewPage /> },
      { path: "question-bank", element: <QuestionBankPage /> },
      { path: "tasks/:taskId", element: <TaskDetailPage /> },
    ],
  },
]);
