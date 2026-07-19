"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      className="flex items-start gap-3 border-l-[3px] border-[var(--danger)] bg-[#fff4f2] px-3 py-2.5 text-[13px] leading-relaxed text-[#973f37]"
      role="alert"
    >
      <span className="min-w-0 flex-1">{message}</span>
      {onRetry && (
        <Button
          variant="ghost"
          size="sm"
          type="button"
          onClick={onRetry}
          className="shrink-0"
        >
          <RefreshCw size={14} />
          重试
        </Button>
      )}
    </div>
  );
}
