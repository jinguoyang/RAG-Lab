import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { LibraryTextPreviewResponse } from "../../types/library";
import { fetchDocumentText } from "../../services/libraryService";

interface TextPreviewProps {
  documentId: string;
  parseRevisionId?: string;
  initialData?: LibraryTextPreviewResponse;
}

export function TextPreview({ documentId, parseRevisionId, initialData }: TextPreviewProps) {
  const [data, setData] = useState<LibraryTextPreviewResponse | null>(initialData ?? null);
  const [fullText, setFullText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setData(initialData ?? null);
    setFullText(null);
    setExpanded(false);
  }, [documentId, parseRevisionId, initialData]);

  // Load preview data when the target document or parse revision changes.
  useEffect(() => {
    if (!data) {
      fetchDocumentText(documentId, "preview", parseRevisionId)
        .then((result) => {
          setData(result as LibraryTextPreviewResponse);
        })
        .catch(() => {});
    }
  }, [data, documentId, parseRevisionId]);

  const handleExpand = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    if (!fullText) {
      setLoading(true);
      try {
        const result = (await fetchDocumentText(documentId, "full", parseRevisionId)) as { text: string };
        setFullText(result.text);
      } finally {
        setLoading(false);
      }
    }
    setExpanded(true);
  };

  const displayText = expanded && fullText ? fullText : data?.text ?? "";

  return (
    <div className="rounded-lg border border-border-cream bg-ivory">
      <div className="flex items-center justify-between border-b border-border-cream px-4 py-2">
        <span className="text-sm font-medium text-near-black">文档预览</span>
        {data?.truncated && (
          <button
            onClick={handleExpand}
            disabled={loading}
            className="flex items-center gap-1 text-xs text-terracotta hover:text-terracotta/80 disabled:opacity-50"
          >
            {loading ? "加载中..." : expanded ? "收起" : "查看全文"}
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        )}
      </div>
      <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap p-4 font-mono text-sm text-near-black">
        {displayText || "暂无预览内容"}
      </pre>
    </div>
  );
}
