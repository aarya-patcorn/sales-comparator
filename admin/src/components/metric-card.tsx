import type { ReactNode } from "react";
import { Card, CardContent } from "./ui/card";

export function MetricCard({
  title,
  value,
  caption,
  icon,
}: {
  title: string;
  value: string;
  caption: string;
  icon: ReactNode;
}) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="relative p-6">
        <div className="absolute right-5 top-5 rounded-2xl bg-primary/10 p-3 text-primary">{icon}</div>
        <p className="text-sm font-medium text-muted">{title}</p>
        <p className="mt-5 text-3xl font-semibold text-foreground">{value}</p>
        <p className="mt-2 text-sm text-muted">{caption}</p>
      </CardContent>
    </Card>
  );
}
