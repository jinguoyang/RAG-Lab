import { useMemo } from "react";

interface MarkdownPreviewProps {
  content: string;
  loading?: boolean;
}

function renderMarkdownToHtml(md: string): string {
  let html = md;

  // Code blocks (``` ... ```)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    const escaped = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return `<pre class="bg-parchment border border-border-cream rounded-md p-4 overflow-x-auto my-3"><code class="text-sm font-mono ${lang ? `language-${lang}` : ""}">${escaped}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="bg-parchment px-1.5 py-0.5 rounded text-sm font-mono text-terracotta">$1</code>');

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3 class="text-base font-serif text-near-black mt-6 mb-2">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="text-lg font-serif text-near-black mt-6 mb-3">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="text-xl font-serif text-near-black mt-6 mb-4">$1</h1>');

  // Bold and italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-info-blue underline" target="_blank" rel="noopener noreferrer">$1</a>');

  // Images
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="max-w-full rounded-md my-2" />');

  // Unordered lists
  html = html.replace(/^[\s]*[-*+] (.+)$/gm, '<li class="ml-4 list-disc">$1</li>');
  html = html.replace(/(<li[^>]*>.*<\/li>\n?)+/g, (match) => `<ul class="my-2 space-y-1">${match}</ul>`);

  // Ordered lists
  html = html.replace(/^[\s]*\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>');

  // Blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-terracotta pl-4 py-1 my-2 text-olive-gray italic">$1</blockquote>');

  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr class="border-border-cream my-4" />');

  // Paragraphs: wrap remaining text blocks
  html = html.replace(/^(?!<[a-z/])((?:(?!<[a-z/]).+\n?)+)/gm, (match) => {
    const trimmed = match.trim();
    if (!trimmed) return "";
    return `<p class="my-2 text-sm text-near-black leading-relaxed">${trimmed}</p>`;
  });

  // Clean up double newlines in paragraphs
  html = html.replace(/\n{2,}/g, "\n");

  return html;
}

export function MarkdownPreview({ content, loading = false }: MarkdownPreviewProps) {
  const html = useMemo(() => renderMarkdownToHtml(content), [content]);

  if (loading) {
    return (
      <div className="text-center py-12">
        <p className="text-stone-gray">加载预览中...</p>
      </div>
    );
  }

  if (!content) {
    return (
      <div className="text-center py-12">
        <p className="text-stone-gray">无预览内容</p>
      </div>
    );
  }

  return (
    <div
      className="bg-white border border-border-cream rounded-md p-6 max-h-[500px] overflow-auto prose prose-sm"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
