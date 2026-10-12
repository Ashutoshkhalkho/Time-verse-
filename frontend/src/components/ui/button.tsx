import * as React from "react";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "danger";
  size?: "sm" | "md" | "lg";
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    const variantStyles = {
      primary: "bg-primary text-white hover:bg-primary-hover shadow-sm",
      secondary: "bg-primary-light text-primary hover:bg-blue-100",
      outline: "border border-surface-border bg-white text-navy hover:bg-gray-50",
      danger: "bg-status-danger text-white hover:bg-red-700",
    };

    const sizeStyles = {
      sm: "h-8 px-3 text-xs rounded-[8px]",
      md: "h-10 px-4 text-sm rounded-[10px]",
      lg: "h-12 px-6 text-base rounded-[12px]",
    };

    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
