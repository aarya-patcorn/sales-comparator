import { toast } from "sonner";

export type ToastTone = "success" | "error" | "warning" | "info";
type ToastInput = { title: string; description?: string; tone: ToastTone };

export function pushToast({ title, description, tone }: ToastInput) {
  toast[tone](title, { description, duration: 4000 });
}

export function useToast() {
  return { pushToast };
}

export function confirmToast(message: string) {
  return new Promise<boolean>((resolve) => {
    let settled = false;
    const finish = (confirmed: boolean) => { if (settled) return; settled = true; resolve(confirmed); };
    toast.warning("Please confirm", {
      description: message,
      duration: Infinity,
      action: { label: "Delete", onClick: () => finish(true) },
      cancel: { label: "Cancel", onClick: () => finish(false) },
      onDismiss: () => finish(false),
    });
  });
}