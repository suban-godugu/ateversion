import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded border text-[12px] font-medium transition-colors disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "border-[var(--line-bright)] bg-[var(--panel)] text-[var(--text)] hover:bg-[var(--panel-2)]",
        ghost: "border-transparent text-[var(--muted)] hover:text-[var(--text)]",
      },
      size: {
        default: "h-8 px-3",
        sm: "h-7 px-2",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";
