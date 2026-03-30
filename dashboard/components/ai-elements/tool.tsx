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
    className: "border-border bg-muted text-muted-foreground",
  },
  "input-available": {
    label: "Running",
    icon: <Loader2Icon className="size-3.5 animate-spin" />,
    className: "border-blue-300/50 bg-blue-100 text-blue-800 dark:border-blue-500/30 dark:bg-blue-900/30 dark:text-blue-200",
  },
  "approval-requested": {
    label: "Awaiting Approval",
    icon: <ShieldAlertIcon className="size-3.5" />,
    className: "border-yellow-300/50 bg-yellow-100 text-yellow-900 dark:border-yellow-500/30 dark:bg-yellow-900/30 dark:text-yellow-200",
  },
  "approval-responded": {
    label: "Responded",
    icon: <ShieldCheckIcon className="size-3.5" />,
    className: "border-slate-300/50 bg-slate-100 text-slate-900 dark:border-slate-500/30 dark:bg-slate-800/40 dark:text-slate-200",
  },
  "output-available": {
    label: "Completed",
    icon: <CheckCircle2Icon className="size-3.5" />,
    className: "border-green-300/50 bg-green-100 text-green-900 dark:border-green-500/30 dark:bg-green-900/30 dark:text-green-200",
  },
  "output-error": {
    label: "Error",
    icon: <OctagonXIcon className="size-3.5" />,
    className: "border-red-300/50 bg-red-100 text-red-900 dark:border-red-500/30 dark:bg-red-900/30 dark:text-red-200",
  },
  "output-denied": {
    label: "Denied",
    icon: <OctagonXIcon className="size-3.5" />,
    className: "border-orange-300/50 bg-orange-100 text-orange-900 dark:border-orange-500/30 dark:bg-orange-900/30 dark:text-orange-200",
  },
};

export function getStatusBadge(state: ToolState): ReactNode {
  const status = STATUS_META[state];
  return (
    <Badge variant="outline" className={cn("inline-flex items-center gap-1.5 text-[11px]", status.className)}>
      {status.icon}
      {status.label}
    </Badge>
  );
}

export type ToolProps = ComponentProps<typeof Collapsible>;

export const Tool = ({ className, ...props }: ToolProps) => (
  <Collapsible className={cn("rounded-md border border-border bg-card/40", className)} {...props} />
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
  <CollapsibleContent className={cn("space-y-2 border-t border-border px-3 py-2", className)} {...props} />
);

export type ToolInputProps = ComponentProps<"div"> & {
  input?: unknown;
};

export const ToolInput = ({ input, className, ...props }: ToolInputProps) => (
  <div className={cn("space-y-1", className)} {...props}>
    <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Input</div>
    <pre className="overflow-x-auto rounded-md bg-background p-2 text-xs text-foreground">
      {JSON.stringify(input ?? {}, null, 2)}
    </pre>
  </div>
);

export type ToolOutputProps = ComponentProps<"div"> & {
  output?: ReactNode;
  errorText?: string | null;
};

export const ToolOutput = ({ output, errorText, className, ...props }: ToolOutputProps) => (
  <div className={cn("space-y-1", className)} {...props}>
    <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Output</div>
    {errorText ? (
      <div className="rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-700 dark:text-red-300">
        {errorText}
      </div>
    ) : (
      <div className="rounded-md bg-background p-2 text-xs text-foreground">{output ?? "No output"}</div>
    )}
  </div>
);
