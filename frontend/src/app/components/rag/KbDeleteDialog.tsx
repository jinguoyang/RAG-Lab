import { useEffect, useState } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../ui/dialog";
import { Button } from "./Button";
import { Input } from "../ui/input";
import type { KbDeleteImpact } from "@/types/knowledgeBase";

interface KbDeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  impact: KbDeleteImpact | null;
  loading: boolean;
  onConfirm: () => void;
  deleting: boolean;
}

export function KbDeleteDialog({
  open,
  onOpenChange,
  impact,
  loading,
  onConfirm,
  deleting,
}: KbDeleteDialogProps) {
  const [confirmName, setConfirmName] = useState("");

  useEffect(() => {
    if (open) {
      setConfirmName("");
    }
  }, [open]);

  const hasBlockers =
    impact &&
    (impact.blockers.activeRagApps.length > 0 || impact.blockers.runningJobs.length > 0);

  const nameMatches = impact && confirmName === impact.kbName;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-border-warm bg-ivory sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="font-serif text-2xl font-medium text-near-black">
            删除知识库
          </DialogTitle>
          <DialogDescription className="text-sm text-olive-gray">
            此操作不可逆，请谨慎操作。
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-center text-stone-gray">加载中...</div>
        ) : impact ? (
          <div className="space-y-4">
            {/* 阻断条件 */}
            {hasBlockers ? (
              <div className="rounded-lg border border-error/30 bg-error/5 p-4">
                <div className="flex items-center gap-2 text-error font-medium mb-2">
                  <AlertTriangle className="w-4 h-4" />
                  无法删除
                </div>
                {impact.blockers.activeRagApps.length > 0 && (
                  <p className="text-sm text-near-black">
                    请先停用或删除以下活跃的智能应用：
                  </p>
                )}
                <ul className="mt-1 space-y-1">
                  {impact.blockers.activeRagApps.map((app) => (
                    <li key={app.appId} className="text-sm text-near-black">
                      · {app.name}
                    </li>
                  ))}
                </ul>
                {impact.blockers.runningJobs.length > 0 && (
                  <p className="text-sm text-near-black mt-2">
                    存在 {impact.blockers.runningJobs.length} 个运行中的任务，请等待完成。
                  </p>
                )}
              </div>
            ) : null}

            {/* 级联影响 */}
            {!hasBlockers && (
              <>
                <div className="rounded-lg border border-border-cream bg-parchment p-4 text-sm text-near-black">
                  <p className="font-medium mb-2">以下数据将被删除：</p>
                  <ul className="space-y-1 text-stone-gray">
                    {impact.cascadeData.bindings > 0 && (
                      <li>· {impact.cascadeData.bindings} 个绑定文档</li>
                    )}
                    {impact.cascadeData.chunks > 0 && (
                      <li>· {impact.cascadeData.chunks} 个向量索引</li>
                    )}
                    {impact.cascadeData.configRevisions > 0 && (
                      <li>· {impact.cascadeData.configRevisions} 个管线配置</li>
                    )}
                    {impact.cascadeData.inactiveRagApps.length > 0 && (
                      <li>
                        · {impact.cascadeData.inactiveRagApps.length} 个已停用的智能应用
                        （{impact.cascadeData.inactiveRagApps.map((a) => a.name).join("、")}）
                      </li>
                    )}
                  </ul>
                  {impact.unaffected.libraryDocuments > 0 && (
                    <p className="mt-2 text-xs text-stone-gray">
                      {impact.unaffected.description}
                    </p>
                  )}
                </div>

                {/* 名称确认 */}
                <div className="space-y-2">
                  <p className="text-sm text-near-black">
                    请输入知识库名称 <span className="font-medium">{impact.kbName}</span> 以确认删除：
                  </p>
                  <Input
                    value={confirmName}
                    onChange={(e) => setConfirmName(e.target.value)}
                    placeholder={impact.kbName}
                    className="border-border-warm"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <Button variant="ghost" onClick={() => onOpenChange(false)}>
                    取消
                  </Button>
                  <Button
                    variant="destructive"
                    disabled={!nameMatches || deleting}
                    onClick={onConfirm}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    {deleting ? "删除中..." : "删除知识库"}
                  </Button>
                </div>
              </>
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
