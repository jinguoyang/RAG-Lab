import { Outlet, NavLink } from "react-router";
import { Users, Building, LogOut, Book } from "lucide-react";
import { Button } from "../components/rag/Button";

export function PlatformLayout() {
  return (
    <div className="flex h-screen bg-parchment">
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
        </nav>

        <div className="p-4 border-t border-border-cream">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-terracotta text-white flex items-center justify-center text-sm font-medium">
              AD
            </div>
            <div>
              <p className="text-sm font-medium text-near-black">管理员用户</p>
              <p className="text-xs text-stone-gray">平台管理员</p>
            </div>
          </div>
          <NavLink to="/login">
            <Button variant="ghost" className="w-full justify-start text-stone-gray hover:text-error-red">
              <LogOut className="w-4 h-4 mr-2" /> 退出登录
            </Button>
          </NavLink>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-14 border-b border-border-cream bg-ivory flex items-center px-6 justify-between shrink-0">
          <div className="text-sm text-stone-gray">平台管理</div>
        </header>
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
