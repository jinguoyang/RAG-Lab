import { Outlet, NavLink } from "react-router";
import { Users, Building, Home, Settings, LogOut, Book } from "lucide-react";
import { Button } from "../components/rag/Button";

export function PlatformLayout() {
  return (
    <div className="flex h-screen bg-parchment">
      {/* Sidebar */}
      <aside className="w-64 bg-ivory border-r border-border-cream flex flex-col">
        <div className="p-4 border-b border-border-cream">
          <h1 className="text-xl font-serif text-terracotta">RAG Platform</h1>
          <p className="text-xs text-stone-gray mt-1">Admin Workspace</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-1">
          <NavLink 
            to="/" 
            end
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <Book className="w-4 h-4" /> Knowledge Bases
          </NavLink>
          <NavLink 
            to="/users" 
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <Users className="w-4 h-4" /> User Management
          </NavLink>
          <NavLink 
            to="/groups" 
            className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
          >
            <Building className="w-4 h-4" /> User Groups
          </NavLink>
        </nav>

        <div className="p-4 border-t border-border-cream">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-full bg-terracotta text-white flex items-center justify-center text-sm font-medium">
              AD
            </div>
            <div>
              <p className="text-sm font-medium text-near-black">Admin User</p>
              <p className="text-xs text-stone-gray">Platform Admin</p>
            </div>
          </div>
          <NavLink to="/login">
            <Button variant="ghost" className="w-full justify-start text-stone-gray hover:text-error-red">
              <LogOut className="w-4 h-4 mr-2" /> Logout
            </Button>
          </NavLink>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-14 border-b border-border-cream bg-ivory flex items-center px-6 justify-between shrink-0">
          <div className="text-sm text-stone-gray">Platform Administration</div>
        </header>
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
