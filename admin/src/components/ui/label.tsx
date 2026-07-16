import type { LabelHTMLAttributes, PropsWithChildren } from "react";
import { cn } from "../../lib/utils";

export function Label({ className, ...props }: PropsWithChildren<LabelHTMLAttributes<HTMLLabelElement>>) {
  return <label className={cn("text-sm font-medium leading-none", className)} {...props} />;
}
