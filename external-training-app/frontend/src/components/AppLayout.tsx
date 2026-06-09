import { NavLink, Outlet } from "react-router";
import {
  BookOpen,
  Library,
  ClipboardCheck,
  FileQuestion,
  Home,
} from "lucide-react";
import { TaskList } from "./TaskList";

const navItems = [
  { to: "/", label: "首页", icon: Home, end: true },
  { to: "/reviews", label: "学习计划", icon: ClipboardCheck },
  { to: "/questions", label: "题目审核", icon: FileQuestion },
  { to: "/question-bank", label: "题库", icon: Library },
];

export function AppLayout() {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-block">
          <div className="brand-mark">
            <BookOpen size={22} aria-hidden="true" />
          </div>
          <div>
            <p className="brand-kicker">External Training</p>
            <h1>员工培训外部应用</h1>
          </div>
        </div>

        <nav className="side-nav" aria-label="主导航">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `side-nav-link${isActive ? " active" : ""}`}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <TaskList />
      </aside>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
