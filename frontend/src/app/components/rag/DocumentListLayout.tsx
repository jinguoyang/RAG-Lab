import { ReactNode } from "react";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./Button";
import { Input } from "./Input";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "./Table";

/** 搜索栏配置 */
export interface SearchConfig {
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
}

/** 状态筛选配置 */
export interface StatusFilterConfig {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}

/** 批量操作按钮配置 */
export interface BatchAction {
  label: string;
  icon?: ReactNode;
  variant?: "outline" | "destructive" | "ghost" | "secondary" | "primary";
  disabled?: boolean;
  onClick: () => void;
}

/** 批量操作栏配置 */
export interface BatchConfig {
  selectedCount: number;
  actions: BatchAction[];
  loading?: boolean;
}

/** 分页配置 */
export interface PaginationConfig {
  total: number;
  pageNo: number;
  totalPages: number;
  loading?: boolean;
  onPageChange: (page: number) => void;
}

/** 表格列配置 */
export interface TableColumn {
  key: string;
  label: string;
  className?: string;
}

/** DocumentListLayout 组件属性 */
export interface DocumentListLayoutProps {
  /** 搜索配置 */
  search?: SearchConfig;
  /** 状态筛选配置 */
  statusFilter?: StatusFilterConfig;
  /** 右侧额外内容（如统计信息） */
  headerExtra?: ReactNode;
  /** 批量操作配置 */
  batch?: BatchConfig;
  /** 表格列配置 */
  columns: TableColumn[];
  /** 表格数据 */
  data: unknown[];
  /** 是否正在加载 */
  loading?: boolean;
  /** 空状态提示 */
  emptyMessage?: string;
  /** 空状态图标 */
  emptyIcon?: ReactNode;
  /** 渲染表格行 */
  renderRow: (item: unknown, index: number) => ReactNode;
  /** 分页配置 */
  pagination?: PaginationConfig;
  /** 是否显示全选复选框 */
  showSelectAll?: boolean;
  /** 全选状态 */
  selectAllChecked?: boolean;
  /** 全选回调 */
  onSelectAll?: (checked: boolean) => void;
  /** 选中的 ID 集合 */
  selectedIds?: Set<string>;
  /** 获取行 ID */
  getRowId?: (item: unknown) => string;
  /** 选中状态变化回调 */
  onSelectionChange?: (ids: Set<string>) => void;
}

/**
 * 通用文档列表布局组件
 *
 * 提供搜索、筛选、批量操作、表格、分页的统一样式和交互。
 * 适用于文档中心、文档库文档列表等场景。
 */
export function DocumentListLayout({
  search,
  statusFilter,
  headerExtra,
  batch,
  columns,
  data,
  loading = false,
  emptyMessage = "暂无数据",
  emptyIcon,
  renderRow,
  pagination,
  showSelectAll = false,
  selectAllChecked = false,
  onSelectAll,
  selectedIds,
  getRowId,
  onSelectionChange,
}: DocumentListLayoutProps) {
  return (
    <div className="space-y-6">
      {/* 搜索和筛选栏 */}
      {(search || statusFilter || headerExtra) && (
        <div className="flex flex-wrap items-center gap-4">
          {search && (
            <div className="relative w-full max-w-80">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray" />
              <Input
                placeholder={search.placeholder || "搜索..."}
                className="pl-9"
                value={search.value}
                onChange={(event) => search.onChange(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") search.onSearch();
                }}
              />
            </div>
          )}
          {search && (
            <Button variant="outline" onClick={search.onSearch}>
              搜索
            </Button>
          )}
          {statusFilter && (
            <select
              className="px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm text-near-black focus:outline-none focus:ring-1 focus:ring-focus-blue"
              value={statusFilter.value}
              onChange={(event) => statusFilter.onChange(event.target.value)}
            >
              {statusFilter.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          )}
          {headerExtra && <div className="ml-auto">{headerExtra}</div>}
        </div>
      )}

      {/* 批量操作栏 */}
      {batch && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border-cream bg-ivory p-4">
          <span className="text-sm text-stone-gray">已选 {batch.selectedCount} 个</span>
          {batch.actions.map((action, index) => (
            <Button
              key={index}
              variant={action.variant || "outline"}
              disabled={loading || batch.loading || batch.selectedCount === 0 || action.disabled}
              onClick={action.onClick}
            >
              {action.icon && <span className="w-4 h-4 mr-2">{action.icon}</span>}
              {action.label}
            </Button>
          ))}
        </div>
      )}

      {/* 表格 */}
      {loading ? (
        <div className="text-center py-12 text-stone-gray">加载中...</div>
      ) : data.length === 0 ? (
        <div className="text-center py-12">
          {emptyIcon || <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-parchment flex items-center justify-center" />}
          <p className="text-stone-gray">{emptyMessage}</p>
        </div>
      ) : (
        <div className="overflow-auto border border-border-cream rounded-xl">
          <Table>
            <TableHeader>
              <TableRow>
                {showSelectAll && (
                  <TableHead className="w-10">
                    <input
                      type="checkbox"
                      checked={selectAllChecked}
                      onChange={(e) => onSelectAll?.(e.target.checked)}
                      className="h-4 w-4 accent-terracotta"
                    />
                  </TableHead>
                )}
                {columns.map((col) => (
                  <TableHead key={col.key} className={col.className}>
                    {col.label}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((item, index) => {
                const rowId = getRowId?.(item);
                const isSelected = rowId && selectedIds?.has(rowId);
                return (
                  <TableRow
                    key={rowId || index}
                    className={isSelected ? "bg-parchment/50" : undefined}
                  >
                    {showSelectAll && rowId && (
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={isSelected || false}
                          onChange={(e) => {
                            if (!onSelectionChange || !selectedIds) return;
                            const next = new Set(selectedIds);
                            if (e.target.checked) next.add(rowId);
                            else next.delete(rowId);
                            onSelectionChange(next);
                          }}
                          className="h-4 w-4 accent-terracotta"
                        />
                      </TableCell>
                    )}
                    {renderRow(item, index)}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* 分页 */}
      {pagination && pagination.total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-stone-gray">
          <span>共 {pagination.total} 个</span>
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
