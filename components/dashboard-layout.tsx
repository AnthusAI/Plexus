"use client"

import { useState } from "react"
import { Book, ChevronLeft, ChevronRight, FileText, Layout, LogOut, Menu, MessageSquare, Settings, User, Users } from "lucide-react"
import Link from "next/link"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

const DashboardLayout = ({ children, signOut }: { children: React.ReactNode; signOut: () => void }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false)

  const menuItems = [
    { name: "Posts", icon: Layout },
    { name: "Drafts", icon: FileText },
    { name: "Research", icon: Book },
    { name: "Topics", icon: MessageSquare },
    { name: "Agents", icon: Users },
    { name: "Brand", icon: User },
  ]

  const Sidebar = () => (
    <div className={`flex h-full flex-col py-4 transition-all duration-300 ${isSidebarCollapsed ? "w-16" : "w-64"}`}>
      <div className="flex items-center justify-between px-4 mb-4">
        <h2 className={`text-lg font-semibold tracking-tight ${isSidebarCollapsed ? "hidden" : "block"}`}>Babulus</h2>
        <Button variant="ghost" size="icon" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
          {isSidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>
      <div className="space-y-1 px-2">
        {menuItems.map((item) => (
          <TooltipProvider key={item.name}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" className={`w-full justify-start ${isSidebarCollapsed ? "px-2" : ""}`}>
                  <item.icon className={`h-4 w-4 ${isSidebarCollapsed ? "" : "mr-2"}`} />
                  {!isSidebarCollapsed && <span>{item.name}</span>}
                </Button>
              </TooltipTrigger>
              {isSidebarCollapsed && <TooltipContent side="right">{item.name}</TooltipContent>}
            </Tooltip>
          </TooltipProvider>
        ))}
      </div>
    </div>
  )

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
        <Sheet open={isSidebarOpen} onOpenChange={setIsSidebarOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden">
              <Menu className="h-6 w-6" />
              <span className="sr-only">Toggle navigation menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-0">
            <Sidebar />
          </SheetContent>
        </Sheet>
        <div className="flex items-center gap-2">
          <Select>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select account" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="account1">Account 1</SelectItem>
              <SelectItem value="account2">Account 2</SelectItem>
              <SelectItem value="account3">Account 3</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="ml-auto flex items-center gap-4">
          <Button variant="ghost" size="icon">
            <Settings className="h-4 w-4" />
            <span className="sr-only">Settings</span>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="rounded-full">
                <img
                  src="/placeholder.svg?height=32&width=32"
                  alt="User avatar"
                  className="rounded-full"
                  width="32"
                  height="32"
                />
                <span className="sr-only">Toggle user menu</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>Profile</DropdownMenuItem>
              <DropdownMenuItem>Settings</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <LogOut className="mr-2 h-4 w-4" />
                <button onClick={signOut}>Sign out</button>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <div className="flex flex-1">
        <aside className="hidden border-r lg:block">
          <ScrollArea className="h-[calc(100vh-3.5rem)]">
            <Sidebar />
          </ScrollArea>
        </aside>
        <main className="flex-1 overflow-y-auto">
          <div className="container mx-auto py-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

export default DashboardLayout