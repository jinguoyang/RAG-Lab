import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { downloadLibraryDocument } from "../../services/libraryService";
import type { ApiDownload } from "../../services/apiClient";

interface PdfPreviewProps {
  documentId: string;
  fileName: string;
  downloadFn?: (documentId: string) => Promise<ApiDownload>;
}

export function PdfPreview({ documentId, fileName, downloadFn }: PdfPreviewProps) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;

    async function loadPdf() {
      setLoading(true);
      setError(null);
      try {
        const fetchFn = downloadFn ?? downloadLibraryDocument;
        const result = await fetchFn(documentId);
        objectUrl = URL.createObjectURL(result.blob);
        setPdfUrl(objectUrl);
      } catch {
        setError("PDF 加载失败");
      } finally {
        setLoading(false);
      }
    }

    void loadPdf();

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  if (loading) {
    return (
      <div className="text-center py-12">
        <p className="text-stone-gray">PDF 加载中...</p>
      </div>
    );
  }

  if (error || !pdfUrl) {
    return (
      <div className="text-center py-12">
        <FileText className="w-12 h-12 mx-auto text-stone-gray mb-4" />
        <p className="text-stone-gray">{error ?? "PDF 加载失败"}</p>
      </div>
    );
  }

  return (
    <div className="border border-border-cream rounded-md overflow-hidden" style={{ height: 600 }}>
      <iframe
        src={pdfUrl}
        title={fileName}
        className="w-full h-full"
        style={{ border: "none" }}
      />
    </div>
  );
}
