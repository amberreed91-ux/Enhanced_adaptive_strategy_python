import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { AIAssistant } from "@/components/AIAssistant";
import {
  LayoutDashboard,
  Database,
  Cpu,
  FlaskConical,
  LineChart,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  LogOut,
  User,
  Activity
} from "lucide-react";

const navGroups = [
  {
    label: "Research Core",
    items: [
      { path: "/", label: "Dashboard", icon: LayoutDashboard },
      { path: "/market-data", label: "Market Data", icon: Database },
      { path: "/features", label: "Feature Generation", icon: Cpu },
    ]
  },
  {
    label: "Testing & Validation",
    items: [
      { path: "/backtests", label: "Backtesting Engine", icon: LineChart },
    ]
  },
  {
    label: "Evolution & Deployment",
    items: [
      { path: "/strategies", label: "Strategy Builder", icon: FlaskConical },
    ]
  },
  {
    label: "System",
    items: [
      { path: "/settings", label: "Settings", icon: Settings },
    ]
  }
];

const NavItem = ({ item, collapsed }) => {
  const location = useLocation();
  const isActive = location.pathname === item.path;
  const Icon = item.icon;

  return (
    <Link to={item.path}>
      <div
        data-testid={`nav-${item.path.replace("/", "") || "dashboard"}`}
        className={`
          flex items-center gap-3 px-3 py-2 rounded-sm text-sm
          transition-colors duration-200
          ${isActive 
            ? "bg-primary/10 text-primary border-l-2 border-primary" 
            : "text-muted-foreground hover:text-foreground hover:bg-white/5"
          }
          ${collapsed ? "justify-center px-2" : ""}
        `}
      >
        <Icon className="w-4 h-4 shrink-0" />
        {!collapsed && <span className="truncate">{item.label}</span>}
      </div>
    </Link>
  );
};

const NavGroup = ({ group, collapsed, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen);

  if (collapsed) {
    return (
      <div className="space-y-1">
        {group.items.map(item => (
          <NavItem key={item.path} item={item} collapsed={collapsed} />
        ))}
      </div>
    );
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="flex items-center justify-between w-full px-3 py-2 text-xs uppercase tracking-widest text-muted-foreground hover:text-foreground">
        <span>{group.label}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? "" : "-rotate-90"}`} />
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-1 mt-1">
        {group.items.map(item => (
          <NavItem key={item.path} item={item} collapsed={collapsed} />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
};

export const AppLayout = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside 
        className={`
          ${collapsed ? "w-16" : "w-64"} 
          sidebar-transition flex flex-col border-r border-border bg-card
        `}
      >
        {/* Logo */}
        <div className="h-14 flex items-center justify-between px-4 border-b border-border">
          {!collapsed && (
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-primary" />
              <span className="font-semibold text-sm">Quant Lab</span>
            </div>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed(!collapsed)}
            className="h-8 w-8"
            data-testid="sidebar-toggle"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </Button>
        </div>

        {/* Navigation */}
        <ScrollArea className="flex-1 py-4">
          <nav className="space-y-4 px-2">
            {navGroups.map((group, idx) => (
              <NavGroup key={idx} group={group} collapsed={collapsed} />
            ))}
          </nav>
        </ScrollArea>

        {/* User Section */}
        <div className="border-t border-border p-3">
          {collapsed ? (
            <Button variant="ghost" size="icon" onClick={logout} className="w-full" data-testid="logout-btn">
              <LogOut className="w-4 h-4" />
            </Button>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center gap-2 px-2">
                <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
                  <User className="w-4 h-4 text-muted-foreground" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{user?.name}</p>
                  <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
                </div>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={logout} 
                className="w-full justify-start text-muted-foreground"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto p-6">
          {children}
        </div>
      </main>

      {/* AI Assistant Widget */}
      <AIAssistant />
    </div>
  );
};
