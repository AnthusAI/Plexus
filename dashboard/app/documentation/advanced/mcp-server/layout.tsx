import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Plexus MCP Server - Plexus Documentation",
  description: "Learn how to use the Plexus MCP server to enable AI agents and tools to interact with Plexus functionality."
};

export default function McpServerLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
} 