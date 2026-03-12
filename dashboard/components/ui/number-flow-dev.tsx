"use client";

import React from "react";

interface NumberFlowProps {
  value: number;
  format?: any;
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
  ...props
}: NumberFlowProps) {
  // Skeleton mode rendering
  if (skeletonMode) {
    return <span className="inline-block h-3 w-8 bg-muted rounded animate-pulse" />;
  }

  // Format the number
  let formattedValue;
  if (format && typeof format === 'object') {
    const options = {
      minimumFractionDigits: format.minimumFractionDigits || 0,
      maximumFractionDigits: format.maximumFractionDigits || 0,
      useGrouping: format.useGrouping !== false
    };
    formattedValue = value.toLocaleString(locales || 'en-US', options);
  } else {
    formattedValue = value.toString();
  }

  // Combine all parts into a single text node for test compatibility
  const combinedText = `${prefix || ''}${formattedValue}${suffix || ''}`;

  return (
    <span {...props}>{combinedText}</span>
  );
}