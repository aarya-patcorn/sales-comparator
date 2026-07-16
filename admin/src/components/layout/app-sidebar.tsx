import { Building2, LayoutDashboard, LogOut, Package, Users } from "lucide-react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { useToast } from "../../lib/toast";
import { getInitials } from "../../lib/utils";
import { Button } from "../ui/button";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "../ui/sidebar";
import { Separator } from "../ui/separator";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard},
  { to: "/users", label: "User Management", icon: Users},
  { to: "/products", label: "Product Management", icon: Package},
  { to: "/competitors", label: "Competitor Management", icon: Building2},
];

export function AppSidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { pushToast } = useToast();

  async function handleLogout() {
    await logout();
    pushToast({ tone: "info", title: "Signed out", description: "Admin session has been cleared." });
    navigate("/login", { replace: true });
  }

  return (
    <Sidebar variant="inset" collapsible="icon" className="border-r border-sidebar-border/70 bg-[#FAFAFA] text-black shadow-lg sticky top-0 z-30 h-screen w-(--sidebar-width) transition-[width] duration-200 ease-linear group-data-[state=collapsed]:w-(--sidebar-collapsed-width) group-data-[collapsible=offcanvas]:fixed group-data-[collapsible=offcanvas]:z-50 group-data-[collapsible=offcanvas]:h-svh group-data-[collapsible=offcanvas]:w-(--sidebar-width) group-data-[collapsible=offcanvas]:transition-none">
      <SidebarHeader className="gap-4 px-0 py-0">
        <div className="flex min-h-16 items-center gap-3 border-sidebar-border/70 bg-sidebar-accent/85 px-3 py-3 text-sidebar-foreground shadow-sm">
          <div className="flex size-11 shrink-0 bg-black text-white items-center justify-center rounded-2xl bg-sidebar-primary text-sm font-semibold text-sidebar-primary-foreground">
            KA
          </div>
          <div className="min-w-0 group-data-[collapsible=icon]:hidden">
            <p className="truncate text-sm font-semibold">Kamdhenu Admin</p>
            <p className="truncate text-xs text-sidebar-foreground/70">Operations workspace</p>
          </div>
        </div>
      </SidebarHeader>

      <hr />

      <SidebarContent className="overflow-x-hidden px-2 py-3">
        <SidebarGroup>
          <SidebarGroupLabel className="text-sidebar-foreground/90">Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname.startsWith(item.to);
                return (
                  <SidebarMenuItem key={item.to}>
                    <SidebarMenuButton
                      render={<NavLink to={item.to} end={item.to === "/dashboard"} />}
                      isActive={isActive}
                      tooltip={item.label}
                      className="h-auto min-h-14 gap-3 rounded-2xl border border-transparent px-3 py-3 transition hover:border-sidebar-border/50 hover:bg-sidebar-accent/30"
                    >
                      <Icon className="size-4 shrink-0" />
                      <div className="min-w-0 group-data-[collapsible=icon]:hidden">
                        <span className="block truncate font-medium">{item.label}</span>
                      </div>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <hr />

      <SidebarFooter className="mt-auto px-3 pb-4 pt-0">
          <Button
            variant="secondary"
            size="sm"
            className="mt-3 w-full justify-start rounded-xl group-data-[collapsible=icon]:hidden"
            onClick={() => void handleLogout()}
          >
            <LogOut className="mr-2 size-4" />
            Sign out
          </Button>
      </SidebarFooter>
    </Sidebar>
  );
}
