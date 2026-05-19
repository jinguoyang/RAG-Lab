import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { LibraryTextPreviewResponse } from "../../types/library";
import { fetchDocumentText } from "../../services/libraryService";

interface TextPreviewProps {
  documentId: string;
  initialData?: LibraryTextPreviewResponse;
}

export function TextPreview({ documentId, initialData }: TextPreviewProps) {
  const [data, setData] = useState<LibraryTextPreviewResponse | null>(initialData ?? null);
  const [fullText, setFullText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  // Load preview data on first render if not provided
  useState(() => {
    if (!data) {
      fetchDocumentText(documentId, "preview")
        .then((result) => {
          setData(result as LibraryTextPreviewResponse);
        })
        .catch(() => {});
    }
  });

  const handleExpand = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    if (!fullText) {
      setLoading(true);
      try {
        const result = (await fetchDocumentText(documentId, "full")) as { text: string };
        setFullText(result.text);
      } finally {
        setLoading(false);
      }
    }
    setExpanded(true);
  };

  const displayText = expanded && fullText ? fullText : data?.text ?? "";

  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-900">
      <div className="flex items-center justify-between border-b border-neutral-700 px-4 py-2">
        <span className="text-sm font-medium text-neutral-300">文档预览</span>
        {data?.truncated && (
          <button
            onClick={handleExpand}
            disabled={loading}
            className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50"
          >
            {loading ? "加载中..." : expanded ? "收起" : "查看全文"}
            {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
          </button>
        )}
      </div>
      <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap p-4 font-mono text-sm text-neutral-200">
        {displayText || "暂无预览内容"}
      </pre>
    </div>
  );
}
