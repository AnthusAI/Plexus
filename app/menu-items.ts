import { Activity, AudioLines, FileBarChart, FlaskConical, ListTodo, Siren, Database, Settings, Sparkles, Inbox } from "lucide-react"
import { LucideIcon } from "lucide-react"

export interface MenuItem {
  name: string
  icon: LucideIcon
  path: string
}

export const menuItems: MenuItem[] = [
  { name: "Activity", icon: Activity, path: "/activity" },
  { name: "Alerts", icon: Siren, path: "/alerts" },
  { name: "Feedback", icon: Inbox, path: "/feedback-queues" },
  { name: "Items", icon: AudioLines, path: "/items" },
  { name: "Reports", icon: FileBarChart, path: "/reports" },
  { name: "Experiments", icon: FlaskConical, path: "/experiments" },
  { name: "Analysis", icon: Sparkles, path: "/analysis" },
  { name: "Scorecards", icon: ListTodo, path: "/scorecards" },
  { name: "Data", icon: Database, path: "/data" },
  { name: "Settings", icon: Settings, path: "/settings" },
]
