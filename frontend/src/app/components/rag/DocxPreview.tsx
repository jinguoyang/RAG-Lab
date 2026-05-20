import { useEffect, useState } from "react";
import mammoth from "mammoth";
import DOMPurify from "dompurify";
import { downloadLibraryDocument } from "../../services/libraryService";

interface DocxPreviewProps {
  documentId: string;
}

export function DocxPreview({ documentId }: DocxPreviewProps) {
  const [html, setHtml] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        setLoading(true);
        setError(null);

        const { blob } = await downloadLibraryDocument(documentId);
        const arrayBuffer = await blob.arrayBuffer();
        const result = await mammoth.convertToHtml({ arrayBuffer });

        if (!cancelled) {
          setHtml(DOMPurify.sanitize(result.value));
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "文档加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  if (loading) {
    return (
      <div className="rounded-lg border border-border-cream bg-ivory p-4">
        <p className="text-sm text-stone-gray">加载中...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-border-cream bg-ivory p-4">
        <p className="text-sm text-error-red">{error}</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border-cream bg-ivory">
      <div className="border-b border-border-cream px-4 py-2">
        <span className="text-sm font-medium text-near-black">文档预览</span>
      </div>
      <div
        className="prose max-h-[500px] overflow-auto p-4"
        dangerouslySetInnerHTML={{ __html: html ?? "" }}
      />
    </div>
  );
}
