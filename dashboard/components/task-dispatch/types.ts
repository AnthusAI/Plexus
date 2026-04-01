// Types for task dispatch configuration

export interface TaskActionBase {
  name: string
  icon: React.ReactNode
  description?: string
}

export interface TaskCommandAction extends TaskActionBase {
  actionType?: 'dispatch'
  command: string | ((data: any) => string)
  target?: string
  dialogType: string
}

export interface TaskUiAction extends TaskActionBase {
  actionType: 'ui'
  onSelect: () => void | Promise<void>
}

export type TaskAction = TaskCommandAction | TaskUiAction

export interface TaskDialogProps {
  action: TaskCommandAction
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
