import { Outlet, NavLink } from "react-router";
import { Users, Building, LogOut, Book, Rocket, ListTree, FolderOpen, UserRound, ChevronUp } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";

export function PlatformLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-parchment">
      {/* Sidebar */}
      <aside className="w-64 bg-ivory border-r border-border-cream flex flex-col">
        <div className="p-4 border-b border-border-cream">
          <h1 className="text-xl font-serif text-terracotta">RAG 平台</h1>
          <p className="text-xs text-stone-gray mt-1">管理工作台</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-1">
          <NavLink 
            to="/" 
            end
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <Book className="w-4 h-4" /> 知识库
          </NavLink>
          <NavLink
            to="/library"
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <FolderOpen className="w-4 h-4" /> 文档库
          </NavLink>
          <NavLink
            to="/rag-apps"
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <Rocket className="w-4 h-4" /> 应用中心
          </NavLink>
          <NavLink 
            to="/users" 
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <Users className="w-4 h-4" /> 用户管理
          </NavLink>
          <NavLink 
            to="/groups" 
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <Building className="w-4 h-4" /> 用户组
          </NavLink>

          <NavLink
            to="/dictionaries"
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <ListTree className="w-4 h-4" /> 字典管理
          </NavLink>

        </nav>

        <div className="p-4 border-t border-border-cream">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex w-full items-center gap-3 rounded-md p-2 text-left transition-colors hover:bg-parchment focus:outline-none focus:ring-2 focus:ring-focus-blue"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-terracotta text-sm font-medium text-white">
                  AD
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-near-black">管理员用户</p>
                  <p className="truncate text-xs text-stone-gray">平台管理员</p>
                </div>
                <ChevronUp className="h-4 w-4 shrink-0 text-stone-gray" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start" className="w-56">
              {/* <DropdownMenuLabel>
                <div className="text-sm font-medium text-near-black">管理员用户</div>
                <div className="text-xs font-normal text-stone-gray">平台管理员</div>
              </DropdownMenuLabel> */}
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled>
                <UserRound className="mr-2 h-4 w-4" /> 个人中心
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild className="text-error-red focus:text-error-red">
                <NavLink to="/login">
                  <LogOut className="mr-2 h-4 w-4" /> 退出登录
                </NavLink>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-14 border-b border-border-cream bg-ivory flex items-center px-6 justify-between shrink-0">
          <div className="text-sm text-stone-gray">平台管理</div>
        </header>
        <div className="flex-1 min-h-0 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
