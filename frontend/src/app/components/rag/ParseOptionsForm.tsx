import { useEffect } from "react";

export interface ParseOptionsFormValues {
  parserName: string;
  contentFormat: "markdown" | "text";
}

interface ParseOptionsFormProps extends ParseOptionsFormValues {
  onParserNameChange: (v: string) => void;
  onContentFormatChange: (v: "markdown" | "text") => void;
  fileName?: string;
}

function getFileExtension(fileName?: string): string {
  if (!fileName) return "";
  return fileName.split(".").pop()?.toLowerCase() ?? "";
}

function getParserOptions(ext: string): { value: string; label: string }[] {
  switch (ext) {
    case "pdf":
      return [
        { value: "auto", label: "自动选择" },
        { value: "pdf_pypdf", label: "pypdf（纯文本提取）" },
        { value: "pdf_plumber", label: "pdfplumber（表格增强）" },
      ];
    case "docx":
      return [
        { value: "auto", label: "自动选择" },
        { value: "markitdown_docx", label: "MarkItDown（Markdown 转换）" },
      ];
    case "xlsx":
      return [
        { value: "auto", label: "自动选择" },
        { value: "markitdown_xlsx", label: "MarkItDown（表格解析）" },
      ];
    case "txt":
    case "md":
      return [{ value: "auto", label: "自动选择" }];
    default:
      return [{ value: "auto", label: "自动选择" }];
  }
}

function getParserLabel(ext: string): string {
  switch (ext) {
    case "pdf":
      return "PDF 解析器";
    case "docx":
      return "Word 解析器";
    case "xlsx":
      return "Excel 解析器";
    default:
      return "解析器";
  }
}

export function ParseOptionsForm({
  parserName,
  onParserNameChange,
  contentFormat,
  onContentFormatChange,
  fileName,
}: ParseOptionsFormProps) {
  const ext = getFileExtension(fileName);
  const parserOptions = getParserOptions(ext);
  const parserLabel = getParserLabel(ext);

  // 文件类型变化时，如果当前解析器不适用于新类型，重置为 auto
  useEffect(() => {
    const validValues = parserOptions.map((o) => o.value);
    if (!validValues.includes(parserName)) {
      onParserNameChange("auto");
    }
  }, [ext, parserName, parserOptions, onParserNameChange]);

  return (
    <>
      <div>
        <label className="mb-1 block text-sm font-medium text-near-black">{parserLabel}</label>
        <select
          className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm"
          value={parserName}
          onChange={(e) => onParserNameChange(e.target.value)}
        >
          {parserOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {ext === "pdf" && (
          <p className="mt-1 text-xs text-stone-gray">仅对 PDF 文件生效，其他格式自动识别</p>
        )}
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-near-black">产物格式</label>
        <select
          className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm"
          value={contentFormat}
          onChange={(e) => onContentFormatChange(e.target.value as "markdown" | "text")}
        >
          <option value="markdown">Markdown</option>
          <option value="text">纯文本</option>
        </select>
      </div>
    </>
  );
}
