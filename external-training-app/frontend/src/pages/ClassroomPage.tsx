import { useState, useEffect, useRef, useCallback } from "react";
import { createSession, submitEvent } from "../services/classroomService";
import { ChoiceQuestion } from "../components/ChoiceQuestion";
import type { ClassroomMessage, ClassroomUiAction, ClassroomEventResponse } from "../types/classroom";

let messageCounter = 0;

function extractErrorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}

export function ClassroomPage() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<(ClassroomMessage & { _key: number })[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [currentState, setCurrentState] = useState("INIT");
  const [uiActions, setUiActions] = useState<ClassroomUiAction[]>([]);
  const [error, setError] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const pushMessage = useCallback((msg: ClassroomMessage) => {
    setMessages((prev) => [...prev, { ...msg, _key: ++messageCounter }]);
  }, []);

  async function handleStartSession() {
    setLoading(true);
    setError("");
    try {
      const result = await createSession("demo-user");
      setSessionId(result.localSessionId || result.sessionId);
      setCurrentState(result.currentState);
      pushMessage({ role: "system", content: "课堂会话已创建。点击「开始学习」进入课程。" });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleEvent(eventType: string, payload?: Record<string, unknown>, query?: string) {
    if (!sessionId) return;
    setLoading(true);
    setError("");
    try {
      if (query) {
        pushMessage({ role: "user", content: query });
      }

      const result: ClassroomEventResponse = await submitEvent(sessionId, eventType, payload, query);

      setCurrentState(result.classroomState);
      setUiActions(result.uiActions || []);

      if (result.visibleContent) {
        pushMessage({
          role: "assistant",
          content: result.visibleContent,
          uiActions: result.uiActions,
        });
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  function handleQuery() {
    if (!input.trim()) return;
    handleEvent("query", {}, input.trim());
    setInput("");
  }

  function handleChoiceAnswer(answer: string) {
    handleEvent("submit_answer", { answer });
    setUiActions([]);
  }

  function handleStructuredAnswer(action: ClassroomUiAction, answer: string) {
    handleEvent("submit_answer", {
      questionId: String(action.data.questionId || ""),
      questionType: action.actionType,
      answer,
    });
    setUiActions([]);
  }

  function renderAction(action: ClassroomUiAction, index: number) {
    if (action.actionType === "button_group") {
      const buttons = (action.data.buttons as { label: string; eventType: string; payload?: Record<string, unknown> }[]) || [];
      return (
        <div key={`action-${index}`} className="flex gap-2 flex-wrap">
          {buttons.map((button) => (
            <button
              key={`${button.eventType}-${button.label}`}
              onClick={() => handleEvent(button.eventType, button.payload || {})}
              disabled={loading}
              className="bg-green-600 text-white px-3 py-1 rounded text-sm disabled:opacity-50"
            >
              {button.label}
            </button>
          ))}
        </div>
      );
    }

    if (action.actionType === "single_choice" || action.actionType === "true_false") {
      return (
        <ChoiceQuestion
          key={`action-${index}`}
          question={String(action.data.content || action.data.question || "请选择")}
          options={(action.data.options as { label: string; text: string }[]) || []}
          onAnswer={(answer) => handleStructuredAnswer(action, answer)}
          disabled={loading}
        />
      );
    }

    if (action.actionType === "subjective") {
      return (
        <div key={`action-${index}`} className="border rounded-lg p-4 bg-blue-50 space-y-3">
          <p className="font-medium">{String(action.data.content || "请输入答案")}</p>
          <textarea
            className="w-full border rounded px-3 py-2 min-h-24"
            disabled={loading}
            placeholder="输入你的回答..."
            onBlur={(event) => {
              const value = event.currentTarget.value.trim();
              if (value) handleStructuredAnswer(action, value);
            }}
          />
        </div>
      );
    }

    return null;
  }

  return (
    <div className="max-w-3xl mx-auto p-6 flex flex-col h-screen">
      <h1 className="text-2xl font-bold mb-4">员工课堂</h1>

      {!sessionId ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">点击按钮开始课堂学习</p>
          <button
            onClick={handleStartSession}
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg disabled:opacity-50"
          >
            {loading ? "创建中..." : "开始学习"}
          </button>
        </div>
      ) : (
        <>
          {/* State indicator */}
          <div className="mb-4 flex items-center gap-2">
            <span className="px-3 py-1 bg-gray-100 rounded-full text-sm">
              状态: {currentState}
            </span>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto space-y-4 mb-4">
            {messages.map((msg) => (
              <div
                key={msg._key}
                className={`p-3 rounded-lg ${
                  msg.role === "user"
                    ? "bg-blue-100 ml-12"
                    : msg.role === "system"
                    ? "bg-gray-100 text-center"
                    : "bg-white border mr-12"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            ))}

            {/* UI Actions */}
            {uiActions.map((action, i) => renderAction(action, i))}

            <div ref={messagesEndRef} />
          </div>

          {/* State transition buttons */}
          <div className="flex gap-2 mb-3 flex-wrap">
            {currentState === "INIT" && (
              <button onClick={() => handleEvent("start", {})}
                disabled={loading} className="bg-green-600 text-white px-3 py-1 rounded text-sm">
                开始学习计划
              </button>
            )}
            {currentState === "PLAN" && (
              <button onClick={() => handleEvent("continue", {})}
                disabled={loading} className="bg-green-600 text-white px-3 py-1 rounded text-sm">
                进入教学
              </button>
            )}
            {currentState === "TEACH" && (
              <button onClick={() => handleEvent("continue", {})}
                disabled={loading} className="bg-purple-600 text-white px-3 py-1 rounded text-sm">
                确认理解
              </button>
            )}
            {currentState === "CHECK_UNDERSTAND" && (
              <button onClick={() => handleEvent("continue", {})}
                disabled={loading} className="bg-purple-600 text-white px-3 py-1 rounded text-sm">
                进入测验
              </button>
            )}
            {currentState === "QUIZ" && (
              <button onClick={() => handleChoiceAnswer("true")}
                disabled={loading} className="bg-blue-600 text-white px-3 py-1 rounded text-sm">
                提交测验
              </button>
            )}
            {currentState === "GRADE" && (
              <button onClick={() => handleEvent("continue", {})}
                disabled={loading} className="bg-blue-600 text-white px-3 py-1 rounded text-sm">
                查看结果
              </button>
            )}
            {currentState === "REVIEW" && (
              <button onClick={() => handleEvent("continue", {})}
                disabled={loading} className="bg-blue-600 text-white px-3 py-1 rounded text-sm">
                课程总结
              </button>
            )}
            {currentState === "SUMMARY" && (
              <>
                <button onClick={() => handleEvent("next_section", {})}
                  disabled={loading} className="bg-blue-600 text-white px-3 py-1 rounded text-sm">
                  下一节
                </button>
                <button onClick={() => handleEvent("complete", {})}
                  disabled={loading} className="bg-green-600 text-white px-3 py-1 rounded text-sm">
                  完成课程
                </button>
              </>
            )}
          </div>

          {/* Input */}
          {currentState !== "COMPLETED" && currentState !== "INIT" && currentState !== "PLAN" && (
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleQuery()}
                placeholder="输入问题..."
                className="flex-1 border rounded px-3 py-2"
                disabled={loading}
              />
              <button
                onClick={handleQuery}
                disabled={loading || !input.trim()}
                className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
              >
                提问
              </button>
            </div>
          )}
        </>
      )}

      {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
    </div>
  );
}
