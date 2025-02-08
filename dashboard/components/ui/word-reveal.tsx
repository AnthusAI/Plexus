"use client";

import { motion, Variants } from "framer-motion";
import { cn } from "@/lib/utils";

interface WordRevealProps {
  text: string;
  className?: string;
  delay?: number;
  gradientWords?: {
    [key: string]: {
      from: string;
      to: string;
    };
  };
}

export default function WordReveal({
  text,
  className,
  delay = 0.15,
  gradientWords = {},
}: WordRevealProps) {
  const words = text.split(" ");

  const container: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: delay },
    },
  };

  const child: Variants = {
    hidden: {
      opacity: 0,
      filter: "blur(10px)",
      y: 20,
    },
    visible: (i: number) => ({
      opacity: 1,
      filter: "blur(0px)",
      y: 0,
      transition: {
        delay: i * delay,
        type: "spring",
        damping: 12,
        stiffness: 100,
      },
    }),
  };

  return (
    <motion.h1
      variants={container}
      initial="hidden"
      animate="visible"
      className={cn(
        "text-center text-4xl font-bold tracking-[-0.02em] text-foreground drop-shadow-sm md:text-7xl md:leading-[5rem]",
        className
      )}
    >
      {words.map((word, i) => {
        const gradient = gradientWords[word];
        return (
          <motion.span
            key={word + i}
            variants={child}
            custom={i}
            className={cn(
              "inline-block mr-[0.25em] last:mr-0 leading-[1.1] pb-[2px]",
              gradient && "text-transparent bg-clip-text bg-gradient-to-r",
              gradient && `from-${gradient.from} to-${gradient.to}`
            )}
          >
            {word}
          </motion.span>
        );
      })}
    </motion.h1>
  );
}
