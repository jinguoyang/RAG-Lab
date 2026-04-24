import { Outlet, NavLink, useParams } from "react-router";
import { LayoutDashboard, FileText, Settings, Stethoscope, History, Network, Shield, ChevronLeft } from "lucide-react";
import { Button } from "../components/rag/Button";
import { Badge } from "../components/rag/Badge";

export function KBLayout() {
  const { kbId } = useParams();

  const navItems = [
    { to: `/kb/${kbId}`, label: "Overview", icon: <LayoutDashboard className="w-4 h-4" />, end: true },
    { to: `/kb/${kbId}/docs`, label: "Document Center", icon: <FileText className="w-4 h-4" /> },
    { to: `/kb/${kbId}/config`, label: "Config Center", icon: <Settings className="w-4 h-4" /> },
    { to: `/kb/${kbId}/qa`, label: "QA Debug", icon: <Stethoscope className="w-4 h-4" /> },
    { to: `/kb/${kbId}/history`, label: "QA History", icon: <History className="w-4 h-4" /> },
    { to: `/kb/${kbId}/graph`, label: "Graph Analysis", icon: <Network className="w-4 h-4" /> },
    { to: `/kb/${kbId}/members`, label: "Members & Permissions", icon: <Shield className="w-4 h-4" /> },
  ];

  return (
    <div className="flex h-screen bg-parchment">
      {/* Sidebar */}
      <aside className="w-64 bg-ivory border-r border-border-cream flex flex-col">
        <div className="p-4 border-b border-border-cream">
          <NavLink to="/">
            <Button variant="ghost" size="sm" className="mb-2 -ml-2 text-stone-gray">
              <ChevronLeft className="w-4 h-4 mr-1" /> Back to Platform
            </Button>
          </NavLink>
          <h1 className="text-xl font-serif text-terracotta truncate" title="Financial Q3 Reports">Financial Q3 Reports</h1>
          <p className="text-xs text-stone-gray mt-1">Knowledge Base Workspace</p>
        </div>
        
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink 
              key={item.to}
              to={item.to}
              end={item.end}
              className={({isActive}) => `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium ${isActive ? 'bg-parchment text-terracotta' : 'text-near-black hover:bg-parchment'}`}
            >
              {item.icon} {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-14 border-b border-border-cream bg-ivory flex items-center px-6 justify-between shrink-0">
          <div className="flex items-center gap-4">
            <span className="text-sm font-medium text-near-black">Financial Q3 Reports</span>
            <div className="flex gap-2">
              <Badge variant="success">Active Config: rev_042</Badge>
              <Badge variant="info">KB ID: {kbId}</Badge>
            </div>
          </div>
          <div className="flex items-center gap-3">
             <div className="text-sm text-stone-gray">KB Admin</div>
             <div className="w-8 h-8 rounded-full bg-olive-gray text-white flex items-center justify-center text-sm font-medium">
              OP
            </div>
          </div>
        </header>
        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
