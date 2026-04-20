"use client";

import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleDashedIcon,
  Loader2Icon,
  OctagonXIcon,
  ShieldAlertIcon,
  ShieldCheckIcon,
} from "lucide-react";
import React from "react";
import type { ComponentProps, ReactNode } from "react";

export type ToolState =
  | "input-streaming"
  | "input-available"
  | "approval-requested"
  | "approval-responded"
  | "output-available"
  | "output-error"
  | "output-denied";

type StatusMeta = {
  label: string;
  icon: ReactNode;
  className: string;
};

const STATUS_META: Record<ToolState, StatusMeta> = {
  "input-streaming": {
    label: "Pending",
    icon: <CircleDashedIcon className="size-3.5" />,
    className: "bg-neutral text-primary-foreground",
  },
  "input-available": {
    label: "Running",
    icon: <Loader2Icon className="size-3.5 animate-spin" />,
    className: "bg-info text-primary-foreground",
  },
  "approval-requested": {
    label: "Awaiting Approval",
    icon: <ShieldAlertIcon className="size-3.5" />,
    className: "bg-warning text-primary-foreground",
  },
  "approval-responded": {
    label: "Responded",
    icon: <ShieldCheckIcon className="size-3.5" />,
    className: "bg-neutral text-primary-foreground",
  },
  "output-available": {
    label: "Completed",
    icon: <CheckCircle2Icon className="size-3.5" />,
    className: "bg-true text-primary-foreground",
  },
  "output-error": {
    label: "Error",
    icon: <OctagonXIcon className="size-3.5" />,
    className: "bg-false text-primary-foreground",
  },
  "output-denied": {
    label: "Denied",
    icon: <OctagonXIcon className="size-3.5" />,
    className: "bg-warning text-primary-foreground",
  },
};

export function getStatusBadge(state: ToolState): ReactNode {
  const status = STATUS_META[state];
  return (
    <Badge variant="pill" className={cn("inline-flex items-center gap-1.5 px-1.5 py-0 text-[11px] font-normal", status.className)}>
      {status.icon}
      {status.label}
    </Badge>
  );
}

export type ToolProps = ComponentProps<typeof Collapsible>;

export const Tool = ({ className, ...props }: ToolProps) => (
  <Collapsible className={cn("rounded-md bg-card/60", className)} {...props} />
);

export type ToolHeaderProps = Omit<ComponentProps<typeof CollapsibleTrigger>, "type"> & {
  toolType: string;
  state: ToolState;
  title?: string;
  toolName?: string;
};

export const ToolHeader = ({
  className,
  toolType,
  state,
  title,
  toolName,
  children,
  ...props
}: ToolHeaderProps) => {
  const label = title || toolName || toolType.replace(/^tool-/, "");
  return (
    <CollapsibleTrigger
      className={cn(
        "flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-xs font-medium",
        "hover:bg-muted/50 [&[data-state=open]>svg]:rotate-180",
        className
      )}
      {...props}
    >
      <div className="min-w-0 flex-1 truncate">{label}</div>
      <div className="flex items-center gap-2">
        {getStatusBadge(state)}
        {children}
        <ChevronDownIcon className="size-4 shrink-0 transition-transform" />
      </div>
    </CollapsibleTrigger>
  );
};

export type ToolContentProps = ComponentProps<typeof CollapsibleContent>;

export const ToolContent = ({ className, ...props }: ToolContentProps) => (
  <CollapsibleContent className={cn("space-y-2 px-3 pb-3", className)} {...props} />
);

export type ToolInputProps = ComponentProps<"div"> & {
  input?: unknown;
};

function formatInputValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try { return JSON.stringify(value); } catch { return String(value); }
}

export const ToolInput = ({ input, className, ...props }: ToolInputProps) => {
  const entries =
    input && typeof input === "object" && !Array.isArray(input)
      ? Object.entries(input as Record<string, unknown>)
      : null;

  return (
    <div className={cn("space-y-1", className)} {...props}>
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Input</div>
      {entries ? (
        <dl className="rounded-md bg-muted/60 p-2 text-xs text-foreground space-y-1">
          {entries.map(([k, v]) => (
            <div key={k} className="flex gap-2 min-w-0">
              <dt className="shrink-0 text-muted-foreground font-medium">{k}:</dt>
              <dd className="truncate font-mono">{formatInputValue(v)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <pre className="overflow-x-auto rounded-md bg-muted/60 p-2 text-xs text-foreground">
          {JSON.stringify(input ?? {}, null, 2)}
        </pre>
      )}
    </div>
  );
};

export type ToolOutputProps = ComponentProps<"div"> & {
  output?: ReactNode;
  errorText?: string | null;
};

export const ToolOutput = ({ output, errorText, className, ...props }: ToolOutputProps) => (
  <div className={cn("space-y-1", className)} {...props}>
    <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Output</div>
    {errorText ? (
      <div className="rounded-md bg-red-500/12 p-2 text-xs text-red-700 dark:text-red-300">
        {errorText}
      </div>
    ) : (
      <div className="rounded-md bg-muted/60 p-2 text-xs text-foreground">{output ?? "No output"}</div>
    )}
  </div>
);
