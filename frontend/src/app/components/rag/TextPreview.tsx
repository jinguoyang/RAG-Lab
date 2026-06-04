import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import { Check, Copy } from "lucide-react";
import type { LibraryTextPreviewResponse } from "../../types/library";
import { fetchDocumentText } from "../../services/libraryService";

interface TextPreviewProps {
  documentId: string;
  parseRevisionId?: string;
  initialData?: LibraryTextPreviewResponse;
  contentFormat?: "markdown" | "text";
  showHeader?: boolean;
  onCopy?: (text: string) => void;
}

export function TextPreview({ documentId, parseRevisionId, initialData, contentFormat = "text", showHeader = true, onCopy }: TextPreviewProps) {
  const [data, setData] = useState<LibraryTextPreviewResponse | null>(initialData ?? null);
  const [fullText, setFullText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const loadingRef = useRef(false);
  const scrollAnchor = useRef<{ scrollTop: number } | null>(null);

  // 重置状态
  useEffect(() => {
    setData(initialData ?? null);
    setFullText(null);
    setLoading(false);
    setError(null);
    setCopied(false);
  }, [documentId, parseRevisionId, initialData]);

  const handleCopy = useCallback(async () => {
    const textToCopy = fullText ?? data?.text ?? "";
    if (!textToCopy) return;

    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      onCopy?.(textToCopy);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = textToCopy;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      onCopy?.(textToCopy);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [fullText, data?.text, onCopy]);

  // 加载预览数据
  useEffect(() => {
    if (!data) {
      fetchDocumentText(documentId, "preview", parseRevisionId)
        .then((result) => {
          setData(result as LibraryTextPreviewResponse);
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : "加载预览失败");
        });
    }
  }, [data, documentId, parseRevisionId]);

  // 滚动到底部时自动加载全文
  useEffect(() => {
    const sentinel = sentinelRef.current;
    const container = containerRef.current;
    if (!sentinel || !container) return;
    if (!data?.truncated || fullText !== null || loadingRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !loadingRef.current) {
          scrollAnchor.current = { scrollTop: container.scrollTop };
          setLoading(true);
          loadingRef.current = true;
          fetchDocumentText(documentId, "full", parseRevisionId)
            .then((result) => {
              setFullText((result as { text: string }).text);
            })
            .catch((err) => {
              setError(err instanceof Error ? err.message : "加载全文失败");
            })
            .finally(() => {
              setLoading(false);
              loadingRef.current = false;
            });
        }
      },
      { root: container, threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [data?.truncated, fullText, documentId, parseRevisionId]);

  // 全文加载完成后恢复滚动位置
  // preview 是全文的前 2000 字符，内容开头一致，直接恢复 scrollTop 即可
  useLayoutEffect(() => {
    if (fullText === null || !scrollAnchor.current) return;
    const container = containerRef.current;
    if (!container) return;

    container.scrollTop = scrollAnchor.current.scrollTop;
    scrollAnchor.current = null;
  }, [fullText]);

  const displayText = fullText ?? data?.text ?? "";
  const showSentinel = data?.truncated && fullText === null;
  const isMarkdown = contentFormat === "markdown";

  return (
    <div className="rounded-lg border border-border-cream bg-ivory">
      {showHeader && (
        <div className="flex items-center justify-between border-b border-border-cream px-4 py-2">
          <span className="text-sm font-medium text-near-black">文档预览</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-stone-gray transition-colors hover:bg-parchment hover:text-near-black"
            title="复制全文"
          >
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5 text-green-600" />
                <span className="text-green-600">已复制</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" />
                <span>复制</span>
              </>
            )}
          </button>
        </div>
      )}
      <div
        ref={containerRef}
        className="max-h-[600px] overflow-auto p-4"
      >
        {error ? (
          <div className="text-center text-red-600">{error}</div>
        ) : displayText ? (
          isMarkdown ? (
            <div className="prose prose-sm max-w-none text-near-black">
              <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{displayText}</ReactMarkdown>
            </div>
          ) : (
            <pre className="whitespace-pre-wrap font-mono text-sm text-near-black">
              {displayText}
            </pre>
          )
        ) : (
          <div className="text-center text-stone-gray">暂无预览内容</div>
        )}
        {showSentinel && (
          <div ref={sentinelRef} className="h-px" />
        )}
        {loading && (
          <div className="flex items-center justify-center gap-2 py-3 text-xs text-stone-gray">
            <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-stone-gray border-t-transparent" />
            正在加载全文...
          </div>
        )}
      </div>
    </div>
  );
}
