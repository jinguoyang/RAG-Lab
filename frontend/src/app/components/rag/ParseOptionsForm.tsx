export interface ParseOptionsFormValues {
  parserName: string;
  contentFormat: "markdown" | "text";
}

interface ParseOptionsFormProps extends ParseOptionsFormValues {
  onParserNameChange: (v: string) => void;
  onContentFormatChange: (v: "markdown" | "text") => void;
}

export function ParseOptionsForm({
  parserName,
  onParserNameChange,
  contentFormat,
  onContentFormatChange,
}: ParseOptionsFormProps) {
  return (
    <>
      <div>
        <label className="mb-1 block text-sm font-medium text-near-black">PDF 解析器</label>
        <select
          className="w-full rounded-md border border-border-cream bg-white px-3 py-2 text-sm"
          value={parserName}
          onChange={(e) => onParserNameChange(e.target.value)}
        >
          <option value="auto">自动选择</option>
          <option value="pdf_pypdf">pypdf（纯文本提取）</option>
          <option value="pdf_plumber">pdfplumber（表格增强）</option>
        </select>
        <p className="mt-1 text-xs text-stone-gray">仅对 PDF 文件生效，其他格式自动识别</p>
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
