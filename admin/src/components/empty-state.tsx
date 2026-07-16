import type { ReactNode } from "react";
import { Card, CardContent } from "./ui/card";

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-4 p-8">
        <div>
          <h3 className="text-lg font-semibold text-foreground">{title}</h3>
          <p className="mt-2 text-sm text-muted">{description}</p>
        </div>
        {action}
      </CardContent>
    </Card>
  );
}
