import type { HTMLAttributes, PropsWithChildren, TableHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export function TableWrapper({ className, ...props }: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return <div className={cn("overflow-hidden rounded-3xl border border-border bg-card shadow-panel", className)} {...props} />;
}

export function Table({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn("min-w-full border-collapse text-left", className)} {...props} />;
}
