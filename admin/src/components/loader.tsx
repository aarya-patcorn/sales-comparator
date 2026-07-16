import { Spinner } from "./ui/spinner";

export function Loader({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex min-h-[260px] items-center justify-center">
      <div className="inline-flex items-center gap-3 rounded-full border border-border/70 bg-card/95 px-4 py-2 text-sm font-medium text-muted-foreground shadow-panel backdrop-blur">
        <Spinner className="size-4 text-primary" />
        {label}
      </div>
    </div>
  );
}
