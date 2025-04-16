import { Activity, AudioLines, FileBarChart, FlaskConical, ListTodo, Siren, Database, Settings, Sparkles, Inbox } from "lucide-react"
import { LucideIcon } from "lucide-react"

export interface MenuItem {
  name: string
  icon: LucideIcon
  path: string
}

export const menuItems: MenuItem[] = [
  { name: "Activity", icon: Activity, path: "/lab/activity" },
  { name: "Alerts", icon: Siren, path: "/lab/alerts" },
  { name: "Feedback", icon: Inbox, path: "/lab/feedback-queues" },
  { name: "Items", icon: AudioLines, path: "/lab/items" },
  { name: "Reports", icon: FileBarChart, path: "/lab/reports" },
  { name: "Evaluation", icon: FlaskConical, path: "/lab/evaluations" },
  { name: "Analysis", icon: Sparkles, path: "/lab/analysis" },
  { name: "Scorecards", icon: ListTodo, path: "/lab/scorecards" },
  { name: "Data", icon: Database, path: "/lab/data" },
  { name: "Settings", icon: Settings, path: "/lab/settings" },
]
