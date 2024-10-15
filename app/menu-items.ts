import { Activity, AudioLines, FileBarChart, FlaskConical, ListTodo, Siren, Database, Settings, Sparkles } from "lucide-react"
import { LucideIcon } from "lucide-react"

export interface MenuItem {
  name: string
  icon: LucideIcon
  path: string
}

export const menuItems: MenuItem[] = [
  { name: "Activity", icon: Activity, path: "/activity" },
  { name: "Alerts", icon: Siren, path: "/alerts" },
  { name: "Items", icon: AudioLines, path: "/items" },
  { name: "Reports", icon: FileBarChart, path: "/reports" },
  { name: "Scorecards", icon: ListTodo, path: "/scorecards" },
  { name: "Experiments", icon: FlaskConical, path: "/experiments" },
  { name: "Optimizations", icon: Sparkles, path: "/optimizations" },
  { name: "Data", icon: Database, path: "/data" },
  { name: "Settings", icon: Settings, path: "/settings" },
]
