import { ReactNode, createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";
import { Button } from "./Button";

interface ConfirmDialogOptions {
  title: string;
  description?: string;
  detail?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  variant?: "default" | "destructive";
}

type ConfirmDialogHandler = (options: ConfirmDialogOptions) => Promise<boolean>;

const ConfirmDialogContext = createContext<ConfirmDialogHandler | null>(null);

/**
 * 提供全局二次确认弹窗。
 * 调用方通过 Promise<boolean> 获取结果，用系统内弹窗替代浏览器原生 confirm。
 */
export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmDialogOptions | null>(null);
  const resolverRef = useRef<((confirmed: boolean) => void) | null>(null);
  const isDestructive = options?.variant === "destructive";

  const closeDialog = useCallback((confirmed: boolean) => {
    resolverRef.current?.(confirmed);
    resolverRef.current = null;
    setOptions(null);
  }, []);

  const confirm = useCallback<ConfirmDialogHandler>((nextOptions) => {
    if (resolverRef.current) {
      resolverRef.current(false);
    }

    setOptions(nextOptions);

    return new Promise((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const contextValue = useMemo(() => confirm, [confirm]);

  return (
    <ConfirmDialogContext.Provider value={contextValue}>
      {children}
      <AlertDialog open={Boolean(options)} onOpenChange={(open) => {
        if (!open) {
          closeDialog(false);
        }
      }}>
        <AlertDialogContent className="border-border-warm bg-ivory p-0 shadow-[0_24px_80px_rgba(20,20,19,0.18)] sm:max-w-[480px]">
          {options && (
            <div className="space-y-5 p-6">
              <AlertDialogHeader className="gap-3 text-left">
                <div className="flex items-start gap-3">
                  <span
                    className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                      isDestructive ? "bg-error-red/10 text-error-red" : "bg-terracotta/10 text-terracotta"
                    }`}
                  >
                    <AlertTriangle className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <AlertDialogTitle className="font-serif text-xl font-medium leading-snug text-near-black">
                      {options.title}
                    </AlertDialogTitle>
                    {options.description && (
                      <AlertDialogDescription className="mt-2 text-sm leading-relaxed text-olive-gray">
                        {options.description}
                      </AlertDialogDescription>
                    )}
                  </div>
                </div>
              </AlertDialogHeader>

              {options.detail && (
                <div className="rounded-lg border border-border-cream bg-parchment p-4 text-sm leading-relaxed text-near-black">
                  {options.detail}
                </div>
              )}

              <AlertDialogFooter className="gap-2">
                <Button variant="ghost" onClick={() => closeDialog(false)}>
                  {options.cancelText ?? "取消"}
                </Button>
                <Button variant={isDestructive ? "destructive" : "primary"} onClick={() => closeDialog(true)}>
                  {options.confirmText ?? "确认"}
                </Button>
              </AlertDialogFooter>
            </div>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </ConfirmDialogContext.Provider>
  );
}

/**
 * 获取全局确认弹窗方法。
 * 必须在 ConfirmDialogProvider 下使用，避免确认逻辑退回浏览器原生弹窗。
 */
export function useConfirmDialog() {
  const confirm = useContext(ConfirmDialogContext);
  if (!confirm) {
    throw new Error("useConfirmDialog must be used within ConfirmDialogProvider");
  }
  return confirm;
}
