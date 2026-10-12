import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "danger" | "secondary";
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variantStyles = {
    default: "bg-primary-light text-primary border-primary/20",
    success: "bg-[#E6F4EA] text-status-success border-status-success/20",
    warning: "bg-[#FEF7E0] text-status-warning border-status-warning/20",
    danger: "bg-[#FCE8E6] text-status-danger border-status-danger/20",
    secondary: "bg-gray-100 text-text-secondary border-surface-border",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-[6px] border px-2 py-0.5 text-xs font-medium transition-colors",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
}
