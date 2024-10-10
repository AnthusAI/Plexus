"use client"

import { useState, useEffect } from "react"
import { Activity, AudioLines, FileBarChart, FlaskConical, ListTodo, LogOut, Menu, PanelLeft, Settings, Sparkles, Siren, Database, Sun, Moon } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

import SquareLogo, { LogoVariant } from './logo-square'

const useMediaQuery = (query: string): boolean => {
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    const media = window.matchMedia(query)
    if (media.matches !== matches) {
      setMatches(media.matches)
    }
    const listener = () => setMatches(media.matches)
    window.addEventListener("resize", listener)
    return () => window.removeEventListener("resize", listener)
  }, [matches, query])

  return matches
}

const DashboardLayout = ({ children, signOut }: { children: React.ReactNode; signOut: () => void }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const { theme, setTheme } = useTheme()
  const isDesktop = useMediaQuery("(min-width: 1024px)")
  const isMobile = useMediaQuery("(max-width: 767px)")

  useEffect(() => {
    if (isDesktop) {
      setIsSidebarOpen(true)
    } else if (isMobile) {
      setIsSidebarOpen(false)
    }
  }, [isDesktop, isMobile])

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen)
  }

  const pathname = usePathname()

  const menuItems = [
    { name: "Activity", icon: Activity, path: "/" },
    { name: "Items", icon: AudioLines, path: "/items" },
    { name: "Alerts", icon: Siren, path: "/alerts" },
    { name: "Reports", icon: FileBarChart, path: "/reports" },
    { name: "Scorecards", icon: ListTodo, path: "/scorecards" },
    { name: "Experiments", icon: FlaskConical, path: "/experiments" },
    { name: "Optimizations", icon: Sparkles, path: "/optimizations" },
    { name: "Data Profiling", icon: Database, path: "/data-profiling" },
    { name: "Settings", icon: Settings, path: "/settings" },
  ]

  const accounts = [
    { name: "Call Criteria", avatar: "/avatar1.png", initials: "CC" },
    { name: "Legal Leads", avatar: "/avatar2.png", initials: "LL" },
    { name: "Snap, Inc", avatar: "/avatar4.png", initials: "SN" },
    { name: "HuggingFace", avatar: "/avatar5.png", initials: "HF" },
    { name: "MATRE", avatar: "/avatar3.png", initials: "M" },
  ]

  const Sidebar = () => (
    <div className="flex flex-col h-full py-2 bg-muted">
      <div className={`mb-4 ${isSidebarOpen ? 'pl-2' : 'pl-3 pr-3'}`}>
        <Link href="/" className={`block ${isSidebarOpen ? 'w-full max-w-md' : 'w-8'}`}>
          {isSidebarOpen ? (
            <SquareLogo variant={LogoVariant.Wide} />
          ) : (
            <SquareLogo variant={LogoVariant.Narrow} />
          )}
        </Link>
      </div>

      <ScrollArea className="flex-grow overflow-y-auto">
        <div className={`space-y-1 ${isSidebarOpen ? 'pl-2' : 'px-3'}`}>
          {menuItems.map((item) => (
            <TooltipProvider key={item.name}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link href={item.path} passHref>
                    <Button
                      variant={pathname === item.path ? "secondary" : "ghost"}
                      className={`w-full justify-start group ${
                        pathname === item.path
                          ? "bg-secondary text-secondary-foreground"
                          : ""
                      } ${isSidebarOpen ? '' : 'px-2'}`}
                    >
                      <item.icon className={`h-4 w-4 group-hover:text-accent-foreground ${
                        isSidebarOpen ? 'mr-2' : ''
                      } flex-shrink-0 ${
                        pathname === item.path ? 'text-secondary-foreground' : 'text-secondary'
                      }`} />
                      {isSidebarOpen && (
                        <span className={pathname === item.path ? 'font-semibold' : ''}>
                          {item.name}
                        </span>
                      )}
                    </Button>
                  </Link>
                </TooltipTrigger>
                {!isSidebarOpen && <TooltipContent side="right">{item.name}</TooltipContent>}
              </Tooltip>
            </TooltipProvider>
          ))}
        </div>
      </ScrollArea>

      <div className="mt-auto px-3 space-y-2 py-4">
        <div className="flex items-center">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  className="p-2 group"
                  onClick={toggleSidebar}
                >
                  <PanelLeft className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {isSidebarOpen && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    className="p-2 group"
                    onClick={toggleTheme}
                  >
                    {theme === "dark" ? (
                      <Sun className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                    ) : (
                      <Moon className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="right">
                  Toggle {theme === "dark" ? "Light" : "Dark"} Mode
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className={`w-full justify-start px-0`}>
              <Avatar className={`h-8 w-8 ${isSidebarOpen ? 'mr-2' : ''}`}>
                <AvatarImage src={accounts[0].avatar} alt={accounts[0].name} />
                <AvatarFallback>{accounts[0].initials}</AvatarFallback>
              </Avatar>
              {isSidebarOpen && <span>{accounts[0].name}</span>}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel>Switch Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {accounts.map((account) => (
              <DropdownMenuItem key={account.name}>
                <Avatar className="h-8 w-8 mr-2">
                  <AvatarImage src={account.avatar} alt={account.name} />
                  <AvatarFallback>{account.initials}</AvatarFallback>
                </Avatar>
                <span>{account.name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className={`w-full justify-start px-0`}>
              <Avatar className={`h-8 w-8 ${isSidebarOpen ? 'mr-2' : ''}`}>
                <AvatarImage src="/user-avatar.png" alt="User avatar" />
                <AvatarFallback>RP</AvatarFallback>
              </Avatar>
              {isSidebarOpen && <span>Ryan Porter</span>}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>My User</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Settings</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <LogOut className="mr-2 h-4 w-4" />
              <button onClick={signOut}>Sign out</button>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark")
  }

  return (
    <div className="flex flex-col min-h-screen">
      <div className="flex flex-1 overflow-hidden bg-muted">
        <aside
          className={`
            fixed top-0 bottom-0 left-0 h-full
            ${isSidebarOpen ? (isMobile ? 'w-14' : 'w-40') : (isMobile ? 'w-0' : 'w-14')}
            transition-all duration-300 ease-in-out overflow-hidden
            ${isMobile && !isSidebarOpen ? 'hidden' : ''}
          `}
        >
          <Sidebar />
        </aside>
        <main 
          className={`flex-1 overflow-y-auto transition-all duration-300 ease-in-out
            ${isMobile && !isSidebarOpen ? 'ml-0' : (isSidebarOpen ? 'ml-40' : 'ml-14')}
            ${isSidebarOpen ? 'p-2' : 'pl-0 pr-2 pt-2 pb-2'}
          `}
        >
          <div className="h-full bg-background rounded-lg">
            <div className="h-full p-6 overflow-y-auto">
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
export default DashboardLayout
