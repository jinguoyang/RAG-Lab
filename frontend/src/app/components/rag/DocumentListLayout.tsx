import type { ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./Button";
import { Input } from "./Input";

interface SearchConfig {
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
}

interface StatusFilterConfig {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}

interface BatchAction {
  label: string;
  icon?: ReactNode;
  variant?: "outline" | "destructive" | "ghost" | "secondary" | "primary";
  disabled?: boolean;
  onClick: () => void;
}

interface BatchConfig {
  selectedCount: number;
  loading?: boolean;
  actions: BatchAction[];
}

interface PaginationConfig {
  total: number;
  pageNo: number;
  totalPages: number;
  loading?: boolean;
  itemLabel?: string;
  onPageChange: (pageNo: number) => void;
}

interface DocumentListLayoutProps {
  search: SearchConfig;
  statusFilter: StatusFilterConfig;
  batch: BatchConfig;
  itemCount: number;
  loading?: boolean;
  emptyState: ReactNode;
  pagination: PaginationConfig;
  children: ReactNode;
}

/**
 * 统一文档类列表的工具栏、批量操作、空态和分页外壳。
 * 表格列和行由调用页面提供，避免公共组件理解具体业务字段。
 */
export function DocumentListLayout({
  search,
  statusFilter,
  batch,
  itemCount,
  loading = false,
  emptyState,
  pagination,
  children,
}: DocumentListLayoutProps) {
  const itemLabel = pagination.itemLabel ?? "文档";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="flex-1 max-w-md">
          <Input
            placeholder={search.placeholder}
            value={search.value}
            onChange={(event) => search.onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                search.onSearch();
              }
            }}
          />
        </div>
        <select
          className="border border-border-cream rounded-md px-3 py-2 text-sm bg-ivory"
          value={statusFilter.value}
          onChange={(event) => statusFilter.onChange(event.target.value)}
        >
          {statusFilter.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <Button variant="secondary" onClick={search.onSearch}>
          搜索
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border-cream bg-ivory p-4">
        <span className="text-sm text-stone-gray">已选 {batch.selectedCount} 个{itemLabel}</span>
        {batch.actions.map((action) => (
          <Button
            key={action.label}
            variant={action.variant ?? "outline"}
            disabled={loading || batch.loading || batch.selectedCount === 0 || action.disabled}
            onClick={action.onClick}
          >
            {action.icon && <span className="mr-2 flex h-4 w-4 items-center justify-center">{action.icon}</span>}
            {action.label}
          </Button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-stone-gray">加载中...</div>
      ) : itemCount === 0 ? (
        <div className="text-center py-12">{emptyState}</div>
      ) : (
        children
      )}

      {pagination.total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-stone-gray">
          <span>共 {pagination.total} 个{itemLabel}</span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={loading || pagination.loading || pagination.pageNo <= 1}
              onClick={() => pagination.onPageChange(pagination.pageNo - 1)}
            >
              <ChevronLeft className="w-4 h-4 mr-1" /> 上一页
            </Button>
            <span className="min-w-20 text-center text-near-black">
              {pagination.pageNo} / {pagination.totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={loading || pagination.loading || pagination.pageNo >= pagination.totalPages}
              onClick={() => pagination.onPageChange(pagination.pageNo + 1)}
            >
              下一页 <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
