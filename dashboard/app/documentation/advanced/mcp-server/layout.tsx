import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Plexus MCP / Tactus Runtime - Plexus Documentation",
  description: "Learn how Plexus exposes one programmable MCP tool backed by the host-provided Plexus Tactus runtime."
};

export default function McpServerLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
