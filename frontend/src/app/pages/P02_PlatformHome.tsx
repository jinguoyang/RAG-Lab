import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Alert } from "../components/rag/Alert";
import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { StatusBadge } from "../components/rag/Badge";
import { Search, Plus } from "lucide-react";
import { toKnowledgeBaseCard } from "../adapters/knowledgeBaseAdapter";
import { fetchKnowledgeBases } from "../services/knowledgeBaseService";
import type { KnowledgeBaseCardViewModel } from "../types/knowledgeBase";

export function PlatformHome() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState("");
  const [kbs, setKbs] = useState<KnowledgeBaseCardViewModel[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      setIsLoading(true);
      setErrorMessage(null);
      fetchKnowledgeBases(keyword)
        .then((page) => {
          if (controller.signal.aborted) {
            return;
          }
          setKbs(page.items.map(toKnowledgeBaseCard));
          setTotal(page.total);
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setErrorMessage("知识库列表读取失败，请确认后端服务和数据库迁移已完成。");
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        });
    }, 250);

    return () => {
      controller.abort();
      window.clearTimeout(timeoutId);
    };
  }, [keyword]);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <PageHeader
        title="知识库"
        description="选择一个知识库进入工作区，或新建知识库。"
        actions={
          <Button variant="primary">
            <Plus className="w-4 h-4 mr-2" />
            新建知识库
          </Button>
        }
      />

      <div className="mt-8 mb-6 flex items-center gap-4">
        <div className="relative w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
          <Input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索知识库..."
            className="pl-9"
          />
        </div>
        <div className="text-sm text-stone-gray ml-auto">
          共显示 {total} 个知识库
        </div>
      </div>

      {errorMessage && (
        <Alert variant="error" title="加载失败" className="mb-6">
          {errorMessage}
        </Alert>
      )}

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[0, 1, 2].map((item) => (
            <Card key={item} className="animate-pulse">
              <CardHeader>
                <div className="h-5 w-2/3 rounded bg-border-warm" />
              </CardHeader>
              <CardContent>
                <div className="h-4 w-full rounded bg-border-cream" />
                <div className="mt-3 h-4 w-1/2 rounded bg-border-cream" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!isLoading && !errorMessage && kbs.length === 0 && (
        <Card>
          <CardContent>
            <p className="text-sm text-stone-gray">暂无可见知识库。</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {!isLoading && !errorMessage && kbs.map((kb) => (
          <Card key={kb.id} className="hover:border-terracotta cursor-pointer transition-colors" onClick={() => navigate(`/kb/${kb.id}`)}>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-start">
                <CardTitle>{kb.name}</CardTitle>
                <StatusBadge status={kb.status} />
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-stone-gray mb-4 line-clamp-2 h-10">{kb.description}</p>
              <div className="text-xs font-mono text-olive-gray">ID: {kb.id}</div>
              <div className="text-xs text-stone-gray mt-1">检索策略：{kb.retrievalSummary}</div>
              <div className="text-xs text-stone-gray mt-1">最近更新：{kb.updatedAtLabel}</div>
            </CardContent>
            <CardFooter className="pt-2">
              <Button variant="ghost" size="sm" className="w-full justify-center">
                进入工作区
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
