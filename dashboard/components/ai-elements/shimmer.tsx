"use client";

import { cn } from "@/lib/utils";
import type { ElementType, HTMLAttributes } from "react";
import { memo } from "react";
import type { CSSProperties } from "react";

export type ShimmerProps<T extends ElementType = "p"> = {
  as?: T;
  duration?: number;
  spread?: number;
  children?: string;
} & Omit<HTMLAttributes<HTMLElement>, "children">;

export const Shimmer = memo(
  <T extends ElementType = "p">({
    as,
    duration = 2,
    spread = 2,
    className,
    children = "",
    style,
    ...props
  }: ShimmerProps<T>) => {
    const Component = (as ?? "p") as ElementType;
    const dynamicSpread = Math.max(spread, Math.ceil(children.length * 0.2));

    return (
      <Component
        className={cn(
          "inline-block !text-transparent bg-clip-text bg-[length:220%_100%]",
          "bg-gradient-to-r from-muted-foreground/40 via-foreground to-muted-foreground/40",
          className
        )}
        style={
          {
            ...style,
            animation: `console-shimmer ${duration}s linear infinite`,
            willChange: "background-position",
            backgroundPosition: `${dynamicSpread}% 50%`,
          } as CSSProperties
        }
        {...props}
      >
        {children}
      </Component>
    );
  }
);

Shimmer.displayName = "Shimmer";
