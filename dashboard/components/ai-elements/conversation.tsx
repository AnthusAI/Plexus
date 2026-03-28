"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ArrowDownIcon } from "lucide-react";
import type { ComponentProps, RefObject } from "react";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";

type ConversationContextValue = {
  scrollRef: React.RefObject<HTMLDivElement | null>;
  isAtBottom: boolean;
  scrollToBottom: () => void;
};

const ConversationContext = createContext<ConversationContextValue | null>(null);

const useConversationContext = () => {
  const context = useContext(ConversationContext);
  if (!context) {
    throw new Error("Conversation components must be rendered within <Conversation />");
  }
  return context;
};

export type ConversationProps = ComponentProps<"div">;

export const Conversation = ({ className, children, ...props }: ConversationProps) => {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) {
      return;
    }

    const updateAtBottom = () => {
      const remaining = node.scrollHeight - node.scrollTop - node.clientHeight;
      setIsAtBottom(remaining <= 24);
    };

    updateAtBottom();
    node.addEventListener("scroll", updateAtBottom);
    return () => node.removeEventListener("scroll", updateAtBottom);
  }, []);

  const value = useMemo<ConversationContextValue>(() => ({
    scrollRef,
    isAtBottom,
    scrollToBottom: () => {
      const node = scrollRef.current;
      if (!node) {
        return;
      }
      node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
    },
  }), [isAtBottom]);

  return (
    <ConversationContext.Provider value={value}>
      <div
        className={cn("relative flex-1 min-h-0 overflow-hidden", className)}
        role="log"
        {...props}
      >
        {children}
      </div>
    </ConversationContext.Provider>
  );
};

export type ConversationContentProps = ComponentProps<"div">;

export const ConversationContent = ({
  className,
  ...props
}: ConversationContentProps) => {
  const { scrollRef } = useConversationContext();

  return (
    <div
      ref={scrollRef as RefObject<HTMLDivElement>}
      className={cn("h-full overflow-y-auto p-4", className)}
      {...props}
    />
  );
};

export type ConversationEmptyStateProps = ComponentProps<"div"> & {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
};

export const ConversationEmptyState = ({
  className,
  title = "No messages yet",
  description = "Start a conversation to see messages here",
  icon,
  children,
  ...props
}: ConversationEmptyStateProps) => (
  <div
    className={cn(
      "flex size-full flex-col items-center justify-center gap-3 p-8 text-center",
      className
    )}
    {...props}
  >
    {children ?? (
      <>
        {icon && <div className="text-muted-foreground">{icon}</div>}
        <div className="space-y-1">
          <h3 className="font-medium text-sm">{title}</h3>
          {description ? (
            <p className="text-muted-foreground text-sm">{description}</p>
          ) : null}
        </div>
      </>
    )}
  </div>
);

export type ConversationScrollButtonProps = ComponentProps<typeof Button>;

export const ConversationScrollButton = ({
  className,
  ...props
}: ConversationScrollButtonProps) => {
  const { isAtBottom, scrollToBottom } = useConversationContext();

  if (isAtBottom) {
    return null;
  }

  return (
    <Button
      className={cn(
        "absolute bottom-4 left-[50%] translate-x-[-50%] rounded-full",
        className
      )}
      onClick={scrollToBottom}
      size="icon"
      type="button"
      variant="outline"
      {...props}
    >
      <ArrowDownIcon className="size-4" />
    </Button>
  );
};
