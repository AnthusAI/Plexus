"use client"

import { useState, useEffect } from "react"
import { AudioLines, FileBarChart, FlaskConical, ListTodo, LogOut, Menu, PanelLeft, Settings, Zap, Siren } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

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

// Custom hook for media query
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
    { name: "Items", icon: AudioLines, path: "/items" },
    { name: "Alerts", icon: Siren, path: "/alerts" },
    { name: "Reports", icon: FileBarChart, path: "/reports" },
    { name: "Scorecards", icon: ListTodo, path: "/scorecards" },
    { name: "Experiments", icon: FlaskConical, path: "/experiments" },
    { name: "Optimizations", icon: Zap, path: "/optimizations" },
    { name: "Settings", icon: Settings, path: "/settings" },
  ]

  const accounts = [
    { name: "Account 1", avatar: "/avatar1.png", initials: "A1" },
    { name: "Account 2", avatar: "/avatar2.png", initials: "A2" },
    { name: "Account 3", avatar: "/avatar3.png", initials: "A3" },
  ]

  const Sidebar = () => (
    <div className="flex h-full flex-col py-4">
      <div className={`mb-4 ${isSidebarOpen ? 'px-3' : 'px-1'}`}>
        <Link href="/" className={`block ${isSidebarOpen ? 'w-full max-w-md' : 'w-8'}`}>
          {isSidebarOpen ? (
            <SquareLogo variant={LogoVariant.Wide} />
          ) : (
            <SquareLogo variant={LogoVariant.Narrow} />
          )}
        </Link>
      </div>
      <ScrollArea className="flex-1">
        <div className={`space-y-1 ${isSidebarOpen ? 'px-3' : 'px-1'}`}>
          {menuItems.map((item) => (
            <TooltipProvider key={item.name}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link href={item.path} passHref>
                    <Button
                      variant="ghost"
                      className={`w-full justify-start ${
                        pathname === item.path ? "bg-gray-100 dark:bg-gray-800" : ""
                      } ${isSidebarOpen ? '' : 'px-2'}`}
                    >
                      <item.icon className={`h-4 w-4 ${isSidebarOpen ? 'mr-2' : ''} flex-shrink-0`} />
                      {isSidebarOpen && <span>{item.name}</span>}
                    </Button>
                  </Link>
                </TooltipTrigger>
                {!isSidebarOpen && <TooltipContent side="right">{item.name}</TooltipContent>}
              </Tooltip>
            </TooltipProvider>
          ))}
        </div>
      </ScrollArea>
      <div className={`mt-auto ${isSidebarOpen ? 'px-3' : 'px-1'}`}>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button 
                variant="ghost" 
                className={`w-full justify-start ${isSidebarOpen ? '' : 'px-2'}`} 
                onClick={toggleSidebar}
              >
                <PanelLeft className="h-4 w-4 flex-shrink-0" />
                {isSidebarOpen && <span className="ml-2"></span>}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              {isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>
  )

  return (
    <div className="flex flex-col min-h-screen">
      <header className="flex h-14 items-center gap-4 border-b bg-gray-100/40 px-6 dark:bg-gray-800/40">
        {isMobile && (
          <Button variant="ghost" size="icon" onClick={toggleSidebar} className="mr-2">
            <Menu className="h-6 w-6" />
            <span className="sr-only">Toggle sidebar</span>
          </Button>
        )}
        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="pl-1">
                <Avatar className="h-8 w-8 mr-2">
                  <AvatarImage src={accounts[0].avatar} alt={accounts[0].name} />
                  <AvatarFallback>{accounts[0].initials}</AvatarFallback>
                </Avatar>
                <span>{accounts[0].name}</span>
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
        </div>
        <div className="ml-auto flex items-center gap-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="rounded-full">
                <Avatar>
                  <AvatarImage src="/user-avatar.png" alt="User avatar" />
                  <AvatarFallback>RP</AvatarFallback>
                </Avatar>
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
      <div className="flex flex-1 overflow-hidden">
        <aside
          className={`
            ${isSidebarOpen ? (isMobile ? 'w-10' : 'w-48') : (isMobile ? 'w-0' : 'w-10')}
            flex-shrink-0 transition-all duration-300 ease-in-out overflow-hidden border-r
            ${isMobile && !isSidebarOpen ? 'hidden' : ''}
          `}
        >
          <Sidebar />
        </aside>
        <main className="flex-1 overflow-y-auto">
          <div className="container mx-auto py-6 px-4">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}

export default DashboardLayout