import { useEffect, useRef, useState } from "react";
import { Search, Loader2 } from "lucide-react";
import { Input } from "./Input";
import { fetchUsers, fetchUserGroups } from "../../services/userGroupService";

interface SubjectSearchDropdownProps {
  subjectType: "user" | "group";
  onSelect: (subjectId: string, label: string) => void;
  excludedIds?: Set<string>;
  excludedLabel?: string;
  placeholder?: string;
  disabled?: boolean;
  inputClassName?: string;
}

export function SubjectSearchDropdown({
  subjectType,
  onSelect,
  excludedIds,
  excludedLabel = "已是成员",
  placeholder,
  disabled = false,
  inputClassName = "",
}: SubjectSearchDropdownProps) {
  const [search, setSearch] = useState("");
  const [users, setUsers] = useState<{ userId: string; displayName: string; username: string; email: string | null }[]>([]);
  const [groups, setGroups] = useState<{ groupId: string; name: string; description: string | null }[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const debounceRef = useRef<number>(0);

  function doSearch(keyword: string, type: "user" | "group") {
    window.clearTimeout(debounceRef.current);
    setLoading(true);
    debounceRef.current = window.setTimeout(() => {
      const trimmed = keyword.trim();
      const fetcher =
        type === "user"
          ? fetchUsers({ keyword: trimmed || undefined, pageNo: 1, pageSize: 8 }).then((p) =>
              setUsers(p.items.filter((u) => u.status === "active")),
            )
          : fetchUserGroups({ keyword: trimmed || undefined, pageNo: 1, pageSize: 8 }).then((p) =>
              setGroups(p.items.filter((g) => g.status === "active")),
            );
      fetcher.catch(() => (type === "user" ? setUsers([]) : setGroups([]))).finally(() => setLoading(false));
    }, 200);
  }

  // 主体类型变化时自动搜索
  useEffect(() => {
    doSearch(search, subjectType);
    return () => window.clearTimeout(debounceRef.current);
  }, [subjectType]);

  const defaultPlaceholder = subjectType === "user" ? "搜索用户名、账号或邮箱" : "搜索用户组名称";

  return (
    <div className="relative">
      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-gray z-10" />
      <Input
        value={search}
        disabled={disabled}
        onChange={(e) => {
          setSearch(e.target.value);
          setOpen(true);
          doSearch(e.target.value, subjectType);
        }}
        onFocus={() => {
          setOpen(true);
          doSearch(search, subjectType);
        }}
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        placeholder={placeholder ?? defaultPlaceholder}
        className={`pl-9 bg-white ${inputClassName}`}
      />
      {open && (
        <div className="absolute left-0 right-0 top-12 z-20 max-h-72 overflow-auto rounded-lg border border-border-cream bg-white shadow-lg">
          {loading ? (
            <div className="flex items-center gap-2 px-3 py-2 text-sm text-stone-gray">
              <Loader2 className="h-4 w-4 animate-spin" />
              搜索中...
            </div>
          ) : subjectType === "user" ? (
            users.length === 0 ? (
              <div className="px-3 py-2 text-sm text-stone-gray">暂无可选用户</div>
            ) : (
              users.map((u) => {
                const excluded = excludedIds?.has(u.userId) ?? false;
                return (
                  <button
                    key={u.userId}
                    type="button"
                    disabled={excluded}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      if (excluded) return;
                      onSelect(u.userId, u.displayName);
                      setSearch(u.displayName);
                      setOpen(false);
                    }}
                    className="w-full px-3 py-2 text-left hover:bg-parchment disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-near-black">{u.displayName}</span>
                      {excluded && <span className="text-xs text-stone-gray">{excludedLabel}</span>}
                    </div>
                    <div className="mt-0.5 text-xs text-stone-gray truncate">
                      @{u.username}{u.email ? ` · ${u.email}` : ""}
                    </div>
                  </button>
                );
              })
            )
          ) : groups.length === 0 ? (
            <div className="px-3 py-2 text-sm text-stone-gray">暂无可选用户组</div>
          ) : (
            groups.map((g) => {
              const excluded = excludedIds?.has(g.groupId) ?? false;
              return (
                <button
                  key={g.groupId}
                  type="button"
                  disabled={excluded}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    if (excluded) return;
                    onSelect(g.groupId, g.name);
                    setSearch(g.name);
                    setOpen(false);
                  }}
                  className="w-full px-3 py-2 text-left hover:bg-parchment disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-near-black">{g.name}</span>
                    {excluded && <span className="text-xs text-stone-gray">{excludedLabel}</span>}
                  </div>
                  {g.description && (
                    <div className="mt-0.5 text-xs text-stone-gray truncate">{g.description}</div>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
