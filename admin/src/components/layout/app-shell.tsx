import { Bell, Search } from "lucide-react";
import { Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "../ui/sidebar";
import { AppSidebar } from "./app-sidebar";

const sectionTitles = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/users", label: "User Management" },
  { to: "/products", label: "Product Management" },
];

export function AppShell() {
  const { user } = useAuth();
  const location = useLocation();

  const currentItem = sectionTitles.find((item) => location.pathname.startsWith(item.to)) ?? sectionTitles[0];

  return (
    <SidebarProvider defaultOpen className="theme min-h-screen bg-transparent">
      <AppSidebar />

      <SidebarInset className="min-w-0 bg-white text-black min-h-screen">
        <header className="sticky top-0 z-20 border-b border-border/70 bg-white shadow-sm">
          <div className="flex min-h-16 items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <SidebarTrigger className="rounded-xl border border-border/70 bg-card shadow-sm" />
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">Admin Workspace</p>
                <h2 className="truncate text-lg font-semibold text-foreground">{currentItem.label}</h2>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <Badge className="rounded-full border-primary/10 bg-primary/10 px-3 py-1 text-primary">
                {user?.role ?? "ADMIN"}
              </Badge>
            </div>
          </div>
        </header>

        <div className="min-w-0 flex-1 overflow-x-hidden">
          <main className="w-full px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
