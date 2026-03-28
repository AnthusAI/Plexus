"use client";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { CornerDownLeftIcon } from "lucide-react";
import type { ComponentProps } from "react";

type PromptSubmitPayload = {
  text?: string;
};

export type PromptInputProps = Omit<ComponentProps<"form">, "onSubmit"> & {
  onPromptSubmit?: (payload: PromptSubmitPayload) => void | Promise<void>;
};

export const PromptInput = ({
  className,
  onPromptSubmit,
  ...props
}: PromptInputProps) => {
  const handleSubmit: ComponentProps<"form">["onSubmit"] = (event) => {
    event.preventDefault();
    if (!onPromptSubmit) {
      return;
    }
    const textarea = event.currentTarget.querySelector("textarea");
    const text = textarea?.value ?? "";
    void onPromptSubmit({ text });
  };

  return (
    <form
      className={cn("w-full rounded-lg border border-border bg-background", className)}
      onSubmit={handleSubmit}
      {...props}
    />
  );
};

export type PromptInputBodyProps = ComponentProps<"div">;

export const PromptInputBody = ({ className, ...props }: PromptInputBodyProps) => (
  <div className={cn("px-3 pt-3", className)} {...props} />
);

export type PromptInputFooterProps = ComponentProps<"div">;

export const PromptInputFooter = ({ className, ...props }: PromptInputFooterProps) => (
  <div
    className={cn("flex items-center justify-between border-t border-border px-3 py-2", className)}
    {...props}
  />
);

export type PromptInputTextareaProps = ComponentProps<typeof Textarea>;

export const PromptInputTextarea = ({
  className,
  rows = 2,
  ...props
}: PromptInputTextareaProps) => (
  <Textarea
    className={cn("min-h-[64px] resize-none border-0 bg-transparent px-0 shadow-none focus-visible:ring-0", className)}
    rows={rows}
    {...props}
  />
);

export type PromptInputSubmitProps = ComponentProps<typeof Button>;

export const PromptInputSubmit = ({
  className,
  children,
  disabled,
  ...props
}: PromptInputSubmitProps) => (
  <Button
    className={cn("gap-1.5", className)}
    disabled={disabled}
    size="sm"
    type="submit"
    {...props}
  >
    {children ?? (
      <>
        Send
        <CornerDownLeftIcon className="size-3.5" />
      </>
    )}
  </Button>
);
