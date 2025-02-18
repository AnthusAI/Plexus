// Types for task dispatch configuration

export interface TaskAction {
  name: string
  icon: React.ReactNode
  command: string | ((data: any) => string)
  target?: string
  dialogType: string
  description?: string
}

export interface TaskDialogProps {
  action: TaskAction
  isOpen: boolean
  onClose: () => void
  onDispatch: (command: string, target?: string) => Promise<void>
}

export interface TaskDispatchConfig {
  buttonLabel: string
  actions: TaskAction[]
  dialogs: Record<string, React.ComponentType<TaskDialogProps>>
}

// Re-export common UI components used by dialogs
export { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
export { Input } from "@/components/ui/input"
export { Label } from "@/components/ui/label"
export { Button } from "@/components/ui/button"
export { Switch } from "@/components/ui/switch"
export { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select" 