"use client";

import React from "react";
import NumberFlow from "@number-flow/react";
import { type Format } from "@number-flow/react";

interface NumberFlowProps {
  value: number;
  format?: Format;
  locales?: string | string[];
  prefix?: string;
  suffix?: string;
  spinTiming?: EffectTiming;
  willChange?: boolean;
  skeletonMode?: boolean;
}

export default function NumberFlowWrapper({
  value,
  format = {},
  locales,
  prefix,
  suffix,
  spinTiming,
  willChange = false,
  skeletonMode = false,
}: NumberFlowProps) {
  // Skeleton mode rendering
  if (skeletonMode) {
    return <span className="inline-block h-3 w-8 bg-muted rounded animate-pulse" />;
  }

  return (
    <span style={{ zIndex: 0, position: 'relative' }}>
      <NumberFlow
        value={value}
        format={format}
        locales={locales}
        prefix={prefix}
        suffix={suffix}
        spinTiming={spinTiming}
        willChange={willChange}
      />
    </span>
  );
}
