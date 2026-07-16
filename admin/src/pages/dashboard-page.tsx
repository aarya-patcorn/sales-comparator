import { Activity, Package, Users, UserCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader } from "../components/loader";
import { MetricCard } from "../components/metric-card";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { fetchAdminMeta, fetchDashboard } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatNumber } from "../lib/utils";
import type { AdminMeta, DashboardMetrics } from "../types/admin";

export function DashboardPage() {
  const { token, user } = useAuth();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [meta, setMeta] = useState<AdminMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    let alive = true;

    async function load() {
      if (!token) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        const [dashboardResponse, metaResponse] = await Promise.all([fetchDashboard(token), fetchAdminMeta(token)]);
        if (alive) {
          setMetrics(dashboardResponse.metrics);
          setMeta(metaResponse);
        }
      } catch (loadError) {
        if (alive) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load dashboard");
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      alive = false;
    };
  }, [token]);

  if (loading) {
    return <Loader label="Loading dashboard..." />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome back, ${user?.name ?? "Admin"}`}
        description="This dashboard is wired to the backend admin metrics and metadata endpoints. Use it to monitor RM user coverage and product catalog health."
        actions={
          <>
            <Button variant="outline" onClick={() => navigate("/users")}>
              Manage users
            </Button>
            <Button onClick={() => navigate("/products")} className="text-white">Manage products</Button>
          </>
        }
      />

      {error ? <p className="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p> : null}

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="RM Users"
          value={formatNumber(metrics?.total_rm_users ?? 0)}
          caption={`${formatNumber(metrics?.active_rm_users ?? 0)} active accounts`}
          icon={<Users className="h-5 w-5" />}
        />
        <MetricCard
          title="Active RM Users"
          value={formatNumber(metrics?.active_rm_users ?? 0)}
          caption="Currently enabled for mobile app access"
          icon={<UserCheck className="h-5 w-5" />}
        />
        <MetricCard
          title="Products"
          value={formatNumber(metrics?.total_products ?? 0)}
          caption={`${formatNumber(metrics?.active_products ?? 0)} active catalog entries`}
          icon={<Package className="h-5 w-5" />}
        />
        <MetricCard
          title="Active Products"
          value={formatNumber(metrics?.active_products ?? 0)}
          caption="Visible in catalog-driven comparisons"
          icon={<Activity className="h-5 w-5" />}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardContent className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground">Backend metadata snapshot</h2>
              <p className="mt-2 text-sm text-muted">These values are loaded from `/api/admin/meta` and used by the management screens.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl bg-background p-4">
                <p className="text-sm font-medium text-muted">Available roles</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {meta?.roles.map((role) => (
                    <Badge key={role}>{role}</Badge>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl bg-background p-4">
                <p className="text-sm font-medium text-muted">Supported product areas</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {meta?.areas.map((area) => (
                    <Badge key={area}>{area}</Badge>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground">Catalog readiness</h2>
              <p className="mt-2 text-sm text-muted">The product editor is prepared for the backend’s supported parameter keys.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {meta?.product_param_keys.map((key) => (
                <Badge key={key} className="bg-primary/10 text-primary">
                  {key}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
