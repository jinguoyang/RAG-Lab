import { AlertTriangle } from "lucide-react";
import { Badge } from "./Badge";
import type { QAPartialDiagnostics } from "../../utils/qaPartialDiagnostics";

interface QAPartialDiagnosticsPanelProps {
  diagnostics?: QAPartialDiagnostics;
  compact?: boolean;
}

function statusVariant(status: string): "warning" | "error" | "info" {
  if (status === "failed") return "error";
  if (status === "partial") return "warning";
  return "info";
}

/**
 * 展示 QARun 部分成功的降级原因、影响说明和受影响 Trace 步骤。
 */
export function QAPartialDiagnosticsPanel({ diagnostics, compact = false }: QAPartialDiagnosticsPanelProps) {
  if (!diagnostics?.hasPartialIssue) return null;

  return (
    <div className="rounded-lg border border-warning-amber/30 bg-warning-amber/10 p-4 text-sm">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning-amber" />
        <div className="min-w-0 flex-1 space-y-3">
          <div>
            <div className="font-medium text-near-black">部分成功详情</div>
            <p className="mt-1 text-stone-gray">{diagnostics.summary}</p>
            {!compact && <p className="mt-1 text-stone-gray">影响：{diagnostics.impact}</p>}
          </div>

          {diagnostics.providerErrors.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {diagnostics.providerErrors.map((error) => (
                <Badge key={error} variant="warning">
                  {error}
                </Badge>
              ))}
            </div>
          )}

          {!compact && diagnostics.affectedSteps.length > 0 && (
            <div className="space-y-2">
              {diagnostics.affectedSteps.map((step) => (
                <div key={step.stepKey} className="rounded-md border border-border-cream bg-ivory p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-near-black">{step.label}</span>
                    <Badge variant={statusVariant(step.status)}>{step.status}</Badge>
                    {step.errorCode && <span className="font-mono text-xs text-error-red">{step.errorCode}</span>}
                  </div>
                  <div className="mt-2 space-y-1 text-xs text-stone-gray">
                    <div>原因：{step.errorMessage || step.reason}</div>
                    <div>影响：{step.impact}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!compact && diagnostics.affectedSteps.length === 0 && (
            <div className="rounded-md border border-border-cream bg-ivory p-3 text-xs text-stone-gray">
              后端没有返回具体 Trace 降级步骤，请结合运行日志或 Provider 监控继续排查。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
