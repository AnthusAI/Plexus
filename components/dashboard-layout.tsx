"use client"

import { useState, useEffect, useRef } from "react"
import { Activity, AudioLines, FileBarChart, FlaskConical, ListTodo, LogOut, Menu, PanelLeft, PanelRight, Settings, Sparkles, Siren, Database, Sun, Moon, Send, Mic, Headphones, MessageCircleMore, MessageSquare, Inbox } from "lucide-react"
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
import { Input } from "@/components/ui/input"
import { ChatExperimentCard } from "@/components/chat-experiment-card"

import SquareLogo, { LogoVariant } from './logo-square'
import { useSidebar } from "@/app/contexts/SidebarContext"

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

const DashboardLayout = ({ children, signOut }: { children: React.ReactNode; signOut: () => Promise<void> }) => {
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true)
  const { rightSidebarState, setRightSidebarState } = useSidebar()
  const { theme, setTheme } = useTheme()
  const isDesktop = useMediaQuery("(min-width: 1024px)")
  const isMobile = useMediaQuery("(max-width: 767px)")

  useEffect(() => {
    if (isDesktop) {
      setIsLeftSidebarOpen(true)
      if (rightSidebarState === 'collapsed') {
        setRightSidebarState('collapsed')
      }
    } else if (isMobile) {
      setIsLeftSidebarOpen(false)
      setRightSidebarState('collapsed')
    }
  }, [isDesktop, isMobile, rightSidebarState, setRightSidebarState])

  const toggleLeftSidebar = () => {
    setIsLeftSidebarOpen(!isLeftSidebarOpen)
  }

  const toggleRightSidebar = () => {
    setRightSidebarState((prevState) => {
      switch (prevState) {
        case 'collapsed':
          return 'normal'
        case 'normal':
          return 'expanded'
        case 'expanded':
          return 'collapsed'
      }
    })
    if (rightSidebarState === 'collapsed') {
      setIsLeftSidebarOpen(false)
    }
  }

  const pathname = usePathname()

  const menuItems = [
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

  const accounts = [
    { name: "Call Criteria", avatar: "/avatar1.png", initials: "CC" },
    { name: "Legal Leads", avatar: "/avatar2.png", initials: "LL" },
    { name: "Snap, Inc", avatar: "/avatar4.png", initials: "SN" },
    { name: "HuggingFace", avatar: "/avatar5.png", initials: "HF" },
    { name: "MATRE", avatar: "/avatar3.png", initials: "M" },
  ]

  const LeftSidebar = () => (
    <div className="flex flex-col h-full py-2 bg-muted">
      <div className={`mb-4 ${isLeftSidebarOpen ? 'pl-2' : 'pl-3 pr-3'}`}>
        <Link href="/" className={`block ${isLeftSidebarOpen ? 'w-full max-w-md' : 'w-8'}`}>
          {isLeftSidebarOpen ? (
            <SquareLogo variant={LogoVariant.Wide} />
          ) : (
            <SquareLogo variant={LogoVariant.Narrow} />
          )}
        </Link>
      </div>

      <ScrollArea className="flex-grow overflow-y-auto">
        <div className={`space-y-1 ${isLeftSidebarOpen ? 'pl-2' : 'px-3'}`}>
          {menuItems.map((item) => (
            <TooltipProvider key={item.name}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Link href={item.path} passHref>
                    <Button
                      variant={
                        (pathname === item.path || 
                        (item.name === "Feedback" && (pathname === "/feedback-queues" || pathname.startsWith("/feedback"))) ||
                        (item.name === "Scorecards" && pathname.startsWith("/scorecards")))
                          ? "secondary"
                          : "ghost"
                      }
                      className={`w-full justify-start group ${
                        (pathname === item.path || 
                        (item.name === "Feedback" && (pathname === "/feedback-queues" || pathname.startsWith("/feedback"))) ||
                        (item.name === "Scorecards" && pathname.startsWith("/scorecards")))
                          ? "bg-secondary text-secondary-foreground"
                          : ""
                      } ${isLeftSidebarOpen ? '' : 'px-2'}`}
                    >
                      <item.icon className={`h-4 w-4 group-hover:text-accent-foreground ${
                        isLeftSidebarOpen ? 'mr-2' : ''
                      } flex-shrink-0 ${
                        (pathname === item.path || 
                        (item.name === "Feedback" && (pathname === "/feedback-queues" || pathname.startsWith("/feedback"))) ||
                        (item.name === "Scorecards" && pathname.startsWith("/scorecards")))
                          ? 'text-secondary-foreground'
                          : 'text-secondary'
                      }`} />
                      {isLeftSidebarOpen && (
                        <span className={
                          (pathname === item.path || 
                          (item.name === "Feedback" && (pathname === "/feedback-queues" || pathname.startsWith("/feedback"))) ||
                          (item.name === "Scorecards" && pathname.startsWith("/scorecards")))
                            ? 'font-semibold'
                            : ''
                        }>
                          {item.name}
                        </span>
                      )}
                    </Button>
                  </Link>
                </TooltipTrigger>
                {!isLeftSidebarOpen && <TooltipContent side="right">{item.name}</TooltipContent>}
              </Tooltip>
            </TooltipProvider>
          ))}
        </div>
      </ScrollArea>

      <div className="mt-auto px-3 space-y-2 py-4">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className={`w-full justify-start px-0`}>
              <Avatar className={`h-8 w-8 ${isLeftSidebarOpen ? 'mr-2' : ''}`}>
                <AvatarImage src={accounts[0].avatar} alt={accounts[0].name} />
                <AvatarFallback className="bg-background dark:bg-border">{accounts[0].initials}</AvatarFallback>
              </Avatar>
              {isLeftSidebarOpen && <span>{accounts[0].name}</span>}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuLabel>Switch Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {accounts.map((account) => (
              <DropdownMenuItem key={account.name}>
                <Avatar className={`h-8 w-8 mr-2 bg-background dark:bg-border`}>
                  <AvatarImage src={account.avatar} alt={account.name} />
                  <AvatarFallback className="bg-muted dark:bg-border">{account.initials}</AvatarFallback>
                </Avatar>
                <span>{account.name}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className={`w-full justify-start px-0`}>
              <Avatar className={`h-8 w-8 ${isLeftSidebarOpen ? 'mr-2' : ''}`}>
                <AvatarImage src="/user-avatar.png" alt="User avatar" />
                <AvatarFallback className="bg-background dark:bg-border">RP</AvatarFallback>
              </Avatar>
              {isLeftSidebarOpen && <span>Ryan Porter</span>}
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

        <div className="flex items-center justify-between">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  className="p-2 group"
                  onClick={toggleLeftSidebar}
                >
                  <PanelLeft className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {isLeftSidebarOpen ? "Toggle sidebar" : "Expand sidebar"}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          {isLeftSidebarOpen && (
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
      </div>
    </div>
  )

  const RightSidebar = () => {
    return (
      <div className="flex flex-col h-full py-2 bg-muted">
        {rightSidebarState === 'collapsed' && (
          <div className="px-3 py-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 p-0 group"
                    onClick={toggleRightSidebar}
                  >
                    <MessageSquare className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left">
                  Expand chat
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        )}
        <div className="flex-grow overflow-hidden">
          <div className="h-full flex flex-col">
            <div className="flex-grow overflow-y-auto flex flex-col-reverse px-4">
              {rightSidebarState !== 'collapsed' && (
                <div className="space-y-4 mb-4">
                  {[
                    <ChatExperimentCard
                      key="exp1"
                      experimentId="Experiment started"
                      status="running"
                      progress={42}
                      accuracy={86.7}
                      elapsedTime="00:02:15"
                      estimatedTimeRemaining="00:03:05"
                      scorecard="CS3 Services v2"
                      score="Good Call"
                    />,
                    <div key="msg1" className="bg-plexus-chat text-plexus-chat-foreground p-3 rounded-lg max-w-[80%]">
                      Okay, I started a new run:
                    </div>,
                    <div key="user1" className="flex items-start space-x-2 justify-end">
                      <div className="bg-user-chat text-user-chat-foreground p-3 rounded-lg max-w-[80%]">
                        Run that again with fresh data.
                      </div>
                      <Avatar className="h-8 w-8 mt-1">
                        <AvatarFallback className="bg-background dark:bg-border">RP</AvatarFallback>
                      </Avatar>
                    </div>,
                    <ChatExperimentCard
                      key="exp2"
                      experimentId="Experiment completed"
                      status="completed"
                      progress={100}
                      accuracy={92}
                      elapsedTime="00:05:12"
                      estimatedTimeRemaining="00:00:00"
                      scorecard="AW IB Sales"
                      score="Pain Points"
                    />,
                    <div key="msg2" className="bg-plexus-chat text-plexus-chat-foreground p-3 rounded-lg max-w-[80%]">
                      The best accuracy was from this version, two days ago, at 92%. That was using a fine-tuned model.
                    </div>,
                    <div key="user2" className="flex items-start space-x-2 justify-end">
                      <div className="bg-user-chat text-user-chat-foreground p-3 rounded-lg max-w-[80%]">
                        What's the best accuracy on Pain Points on AW IB Sales?
                      </div>
                      <Avatar className="h-8 w-8 mt-1">
                        <AvatarFallback className="bg-background dark:bg-border">DN</AvatarFallback>
                      </Avatar>
                    </div>,
                    <ChatExperimentCard
                      key="exp3"
                      experimentId="New experiment"
                      status="running"
                      progress={87}
                      accuracy={88.2}
                      elapsedTime="00:04:35"
                      estimatedTimeRemaining="00:00:40"
                      scorecard="CS3 Services v2"
                      score="Good Call"
                    />,
                    <div key="msg3" className="bg-plexus-chat text-plexus-chat-foreground p-3 rounded-lg max-w-[80%]">
                      Certainly! I'm starting a new experiment run for the "CS3 Services v2" scorecard on the "Good Call" score.
                    </div>,
                    <div key="user3" className="flex items-start space-x-2 justify-end">
                      <div className="bg-user-chat text-user-chat-foreground p-3 rounded-lg max-w-[80%]">
                        Start a new experiment run on the "CS3 Services v2" scorecard for the "Good Call" score.
                      </div>
                      <Avatar className="h-8 w-8 mt-1">
                        <AvatarFallback className="bg-background dark:bg-border">RP</AvatarFallback>
                      </Avatar>
                    </div>,
                  ].reverse()}
                </div>
              )}
            </div>
          </div>
        </div>
        {rightSidebarState !== 'collapsed' && (
          <div className="px-4 pt-4 pb-2 border-t border-border">
            <form className="flex items-center">
              <Input 
                type="text" 
                placeholder="Type a message..." 
                className="flex-grow mr-2 bg-background" 
              />
              <Button type="submit" size="icon">
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        )}
        <div className="px-3 pt-1 pb-2 flex justify-between items-center">
          {rightSidebarState !== 'collapsed' && (
            <div className="flex space-x-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 p-0 group"
                    >
                      <Mic className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    Dictate Message
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 p-0 group"
                    >
                      <Headphones className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    Voice Mode
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          )}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 p-0 ml-auto group"
                  onClick={toggleRightSidebar}
                >
                  <PanelRight className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">
                {rightSidebarState === 'collapsed' ? "Expand chat" : "Collapse chat"}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
    )
  }

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark")
  }

  useEffect(() => {
    document.body.classList.add('bg-muted')
    return () => {
      document.body.classList.remove('bg-muted')
    }
  }, [])

  return (
    <div className="flex flex-col h-screen bg-muted">
      <div className="flex flex-1 overflow-hidden bg-muted">
        <aside
          className={`
            fixed top-0 bottom-0 left-0 h-full
            ${isLeftSidebarOpen ? (isMobile ? 'w-14' : 'w-40') : (isMobile ? 'w-0' : 'w-14')}
            transition-all duration-300 ease-in-out overflow-hidden
            ${isMobile && !isLeftSidebarOpen ? 'hidden' : ''}
          `}
        >
          <LeftSidebar />
        </aside>
        <main 
          className={`flex-1 flex flex-col transition-all duration-300 ease-in-out
            ${isMobile && !isLeftSidebarOpen ? 'ml-0' : (isLeftSidebarOpen ? 'ml-40' : 'ml-14')}
            ${isMobile && rightSidebarState === 'collapsed' ? 'mr-0' : 
              rightSidebarState === 'normal' ? 'mr-80' : 
              rightSidebarState === 'expanded' ? 'mr-[40%]' : 'mr-14'}
            ${isLeftSidebarOpen ? 'pl-2' : 'pl-0'}
            ${rightSidebarState !== 'collapsed' ? 'pr-2' : 'pr-0'}
            pt-2 pb-2
          `}
        >
          <div className="flex-1 flex flex-col bg-background rounded-lg overflow-hidden">
            <div className="flex-1 overflow-y-auto">
              <div className="h-full pt-2 pr-4 pb-0 pl-4">
                {children}
              </div>
            </div>
          </div>
        </main>
        <aside
          className={`
            fixed top-0 bottom-0 right-0 h-full
            ${rightSidebarState === 'collapsed' ? (isMobile ? 'w-0' : 'w-14') :
              rightSidebarState === 'normal' ? (isMobile ? 'w-14' : 'w-80') :
              'w-[40%]'}
            transition-all duration-300 ease-in-out overflow-hidden
            ${isMobile && rightSidebarState === 'collapsed' ? 'hidden' : ''}
          `}
        >
          <RightSidebar />
        </aside>
      </div>
    </div>
  )
}

export default DashboardLayout
