"use client"

import * as React from "react"
import { useState, useEffect, useRef } from "react"
import { Activity, StickyNote, FileBarChart, FlaskConical, ListChecks, LogOut, Menu, PanelLeft, PanelRight, Settings, Sparkles, Siren, HardDriveDownload, Sun, Moon, Send, Mic, Headphones, MessageCircleMore, MessageSquare, Inbox, X, ArrowLeftRight, Layers3, Monitor, CircleHelp, Gauge, Waypoints } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import { generateClient } from "aws-amplify/data"
import { listFromModel } from "@/utils/amplify-helpers"
import type { Schema } from "@/amplify/data/resource"
import type { AccountSettings } from "@/types/account-config"
import { isValidAccountSettings } from "@/types/account-config"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button, type ButtonProps } from "@/components/ui/button"
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
import { ChatEvaluationCard } from "@/components/chat-evaluation-card"

import BrandableLogo from './BrandableLogo'
import { LogoVariant } from './logo-square'
import { useSidebar } from "@/app/contexts/SidebarContext"
import { useAccount } from "@/app/contexts/AccountContext"
import { DashboardDrawer } from "@/components/DashboardDrawer"
import { Spinner } from "@/components/ui/spinner"

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

const DashboardButton = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => (
    <Button ref={ref} className={`!rounded-[6px] ${className}`} {...props} />
  )
)
DashboardButton.displayName = "DashboardButton"

const MobileHeader = ({ 
  toggleLeftSidebar, 
  toggleRightSidebar, 
  rightSidebarState 
}: { 
  toggleLeftSidebar: () => void;
  toggleRightSidebar: () => void;
  rightSidebarState: 'collapsed' | 'normal' | 'expanded';
}) => (
  <div className="hidden max-lg:flex items-center justify-between p-0.5 px-2 bg-background min-h-[3rem] mobile-header">
    <DashboardButton
      variant="ghost"
      size="sm"
      onClick={toggleLeftSidebar}
      className="h-8 w-8 p-0 ml-3"
    >
      <Menu className="h-4 w-4" />
    </DashboardButton>
    
    <div className="flex-1" /> {/* Spacer - logo removed per user request */}

    <DashboardButton
      variant="ghost"
      size="sm"
      onClick={toggleRightSidebar}
      className="h-8 w-8 p-0 mr-3 hidden xs:block"
    >
      <MessageSquare className="h-4 w-4" />
    </DashboardButton>
  </div>
)

const client = generateClient<Schema>()

type Account = Schema['Account']['type']

export const menuItems = [
  { name: "Items", icon: StickyNote, path: "/lab/items" },
  { name: "Feedback", icon: MessageCircleMore, path: "/lab/feedback-queues" },
  { name: "Reports", icon: FileBarChart, path: "/lab/reports" },
  { name: "Evaluations", icon: FlaskConical, path: "/lab/evaluations" },
  { name: "Procedures", icon: Waypoints, path: "/lab/procedures" },
  { name: "Scorecards", icon: ListChecks, path: "/lab/scorecards" },
  { name: "Sources", icon: HardDriveDownload, path: "/lab/sources" },
  { name: "Batches", icon: Layers3, path: "/lab/batches" },
  { name: "Activity", icon: Activity, path: "/lab/activity" },
  { name: "Alerts", icon: Siren, path: "/lab/alerts" },
  { name: "Help", icon: CircleHelp, path: "/documentation" },
]

const DashboardLayout = ({ children, signOut }: { children: React.ReactNode; signOut: () => Promise<void> }) => {
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true)
  const [isDashboardDrawerOpen, setIsDashboardDrawerOpen] = useState(false)
  const [isNavigating, setIsNavigating] = useState(false)
  const [loadingRoute, setLoadingRoute] = useState<string | null>(null)
  const { rightSidebarState, setRightSidebarState } = useSidebar()
  const { theme, setTheme } = useTheme()
  const isDesktop = useMediaQuery("(min-width: 768px)")
  const isMobile = useMediaQuery("(max-width: 767px)")
  const { accounts, selectedAccount, isLoadingAccounts, visibleMenuItems, setSelectedAccount, refetchAccounts } = useAccount()
  const pathname = usePathname()

  // Handle navigation loading states
  useEffect(() => {
    const handleRouteChangeStart = () => {
      setIsNavigating(true)
    }
    
    const handleRouteChangeComplete = () => {
      setIsNavigating(false)
      setLoadingRoute(null)
    }

    // Reset loading state when pathname changes (navigation complete)
    setIsNavigating(false)
    setLoadingRoute(null)
  }, [pathname])

  const handleNavClick = (path: string) => {
    if (path !== pathname) {
      setLoadingRoute(path)
      setIsNavigating(true)
      
      // Auto-hide left sidebar on mobile after navigation
      if (isMobile && isLeftSidebarOpen) {
        setIsLeftSidebarOpen(false)
      }
    }
  }

  useEffect(() => {    
    if (isDesktop) {
      setIsLeftSidebarOpen(true)
    } else if (isMobile) {
      setIsLeftSidebarOpen(false)
    }
  }, [isDesktop, isMobile])

  const toggleLeftSidebar = () => {
    setIsLeftSidebarOpen(!isLeftSidebarOpen)
  }

  const toggleRightSidebar = () => {
    console.log('Toggle Right Sidebar:', {
      isMobile,
      currentState: rightSidebarState,
      willSetTo: rightSidebarState === 'collapsed' ? 'normal' : 'collapsed'
    });

    if (isMobile) {
      // On mobile, just toggle between collapsed and normal
      setRightSidebarState(prevState => {
        const newState = prevState === 'collapsed' ? 'normal' : 'collapsed';
        return newState;
      });
      
      // Close left sidebar when opening chat on mobile
      if (rightSidebarState === 'collapsed') {
        setIsLeftSidebarOpen(false);
      }
    } else {
      // Desktop behavior remains the same
      setRightSidebarState((prevState) => {
        const newState = prevState === 'collapsed' ? 'normal' : 
                        prevState === 'normal' ? 'expanded' : 'collapsed';
        console.log('Setting desktop right sidebar state:', {
          from: prevState,
          to: newState
        });
        return newState;
      });
    }
  }

  // Keyboard shortcut for dashboard drawer (.) - only on /lab/ paths
  useEffect(() => {
    const isLabPath = pathname.startsWith('/lab/')
    if (!isLabPath) return

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === '.' && !event.ctrlKey && !event.metaKey && !event.altKey) {
        // Only trigger if not focused on an input/textarea
        const activeElement = document.activeElement
        if (activeElement && (
          activeElement.tagName === 'INPUT' || 
          activeElement.tagName === 'TEXTAREA' ||
          activeElement.getAttribute('contenteditable') === 'true'
        )) {
          return
        }
        
        event.preventDefault()
        setIsDashboardDrawerOpen(prev => !prev)
      }
    }
    
    document.addEventListener('keydown', handleKeydown)
    return () => document.removeEventListener('keydown', handleKeydown)
  }, [pathname])

  const toggleDashboardDrawer = () => {
    setIsDashboardDrawerOpen(prev => !prev)
  }

  const isActivityRoute = pathname === "/lab/activity" || pathname.startsWith("/lab/tasks/");

  const LeftSidebar = () => {
    return (
      <div className={`flex flex-col h-full py-2 bg-frame ${isMobile ? 'pr-2 mobile-compact' : ''}`}>
        <div className={`mb-4 ${isLeftSidebarOpen ? 'pl-2' : ''}`}>
          <Link href="/" className={`block ${isLeftSidebarOpen ? 'w-full max-w-md' : 'w-12 pl-4'}`}>
              {isLeftSidebarOpen ? (
              <BrandableLogo variant={LogoVariant.Wide} />
              ) : (
              <BrandableLogo variant={LogoVariant.Narrow} />
              )}
          </Link>
        </div>

        <div className="flex-grow">
          <div className={`${isLeftSidebarOpen ? 'pl-2' : 'px-3 w-16'} ${isMobile ? 'space-y-2' : 'space-y-1'}`}>
            {visibleMenuItems.map((item) => {
              const isCurrentPage = (pathname === item.path ||
                (item.name === "Feedback" && (pathname === "/feedback-queues" || pathname.startsWith("/feedback"))) ||
                (item.name === "Items" && pathname.startsWith(item.path)) ||
                (item.name === "Evaluations" && pathname.startsWith(item.path)) ||
                (item.name === "Procedures" && pathname.startsWith(item.path)) ||
                (item.name === "Templates" && pathname.startsWith(item.path)) ||
                (item.name === "Scorecards" && pathname.startsWith(item.path)) ||
                (item.name === "Reports" && pathname.startsWith(item.path)) ||
                (item.name === "Sources" && pathname.startsWith(item.path)) ||
                (item.name === "Activity" && isActivityRoute))
              
              const isLoading = loadingRoute === item.path
              
              return (
                <Link 
                  key={item.name}
                  href={item.path}
                  onClick={() => handleNavClick(item.path)}
                  className={`flex items-center w-full px-3 py-2 group !rounded-[4px] relative transition-all duration-200 ${
                    isCurrentPage
                      ? "bg-selected text-selected-foreground"
                      : "hover:bg-accent hover:text-accent-foreground"
                  } ${isLeftSidebarOpen ? '' : 'px-2'} ${
                    isMobile ? 'py-3' : ''
                  } ${isLoading ? 'opacity-75' : ''}`}
                >
                  <div className={`relative ${isLoading ? 'animate-pulse' : ''}`}>
                    <item.icon className={`h-4 w-4 flex-shrink-0 transition-all duration-200 ${
                      isCurrentPage
                        ? "text-selected-foreground"
                        : "text-navigation-icon"
                    } ${isLoading ? 'opacity-50' : ''}`} />
                    {isLoading && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-2 h-2 bg-primary rounded-full animate-ping" />
                      </div>
                    )}
                  </div>
                  {isLeftSidebarOpen && (
                    <span className={`ml-3 transition-all duration-200 ${isLoading ? 'opacity-75' : ''}`}>
                      {item.name}
                    </span>
                  )}
                  {/* Loading progress bar */}
                  {isLoading && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary/20 overflow-hidden">
                      <div className="h-full bg-primary animate-loading-bar" />
                    </div>
                  )}
                </Link>
              )
            })}
          </div>
        </div>

        <div className="mt-auto pl-2 space-y-2 py-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className={`w-full justify-start px-2 pr-2 cursor-pointer`}
              >
                <Avatar className={`h-8 w-8 ${isLeftSidebarOpen ? 'mr-2' : ''}`}>
                  <AvatarImage 
                    src={`/avatar-${selectedAccount?.key || '1'}.png`} 
                    alt={selectedAccount?.name || 'Account'} 
                  />
                  <AvatarFallback className="bg-background dark:bg-border">
                    {isLoadingAccounts ? (
                      <Spinner className="h-4 w-4" />
                    ) : (
                      selectedAccount?.name?.split(' ').map(word => word[0]).join('') || 'AC'
                    )}
                  </AvatarFallback>
                </Avatar>
                {isLeftSidebarOpen && (
                  <span className="text-muted-foreground">
                    {isLoadingAccounts ? 'Loading accounts...' : selectedAccount?.name || 'Select Account'}
                  </span>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-[200px] z-[9999]">
              <DropdownMenuItem 
                className={`cursor-pointer ${!pathname.startsWith('/lab/') ? 'opacity-50' : ''}`} 
                onClick={pathname.startsWith('/lab/') ? toggleDashboardDrawer : undefined}
              >
                <Gauge className="mr-2 h-4 w-4 text-navigation-icon" />
                Dashboard
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <Link href="/settings">
                <DropdownMenuItem className="cursor-pointer">
                  <Settings className="mr-2 h-4 w-4 text-navigation-icon" />
                  Settings
                </DropdownMenuItem>
              </Link>
              <DropdownMenuSeparator />
              <DropdownMenu>
                <DropdownMenuTrigger className="w-full">
                  <DropdownMenuItem className="cursor-pointer">
                    <ArrowLeftRight className="mr-2 h-4 w-4" />
                    Select Account
                  </DropdownMenuItem>
                </DropdownMenuTrigger>
                <DropdownMenuContent side="right" align="start" className="w-[200px] z-[9999]">
                  {isLoadingAccounts ? (
                    <DropdownMenuItem className="flex items-center">
                      <Spinner className="mr-2 h-4 w-4" />
                      Loading accounts...
                    </DropdownMenuItem>
                  ) : accounts.length === 0 ? (
                    <>
                      <DropdownMenuItem className="text-muted-foreground">
                        No accounts available
                      </DropdownMenuItem>
                      <DropdownMenuItem 
                        className="cursor-pointer text-primary"
                        onClick={() => refetchAccounts()}
                      >
                        <ArrowLeftRight className="mr-2 h-4 w-4" />
                        Retry Loading
                      </DropdownMenuItem>
                    </>
                  ) : (
                    accounts.map((account) => (
                      <DropdownMenuItem 
                        key={account.id} 
                        className={`cursor-pointer ${selectedAccount?.id === account.id ? 'bg-accent' : ''}`}
                        onClick={() => setSelectedAccount(account)}
                      >
                        <Avatar className="h-6 w-6 mr-2">
                          <AvatarImage 
                            src={`/avatar-${account.key}.png`} 
                            alt={account.name} 
                          />
                          <AvatarFallback className="bg-frame dark:bg-border text-xs">
                            {account.name.split(' ').map(word => word[0]).join('')}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex flex-col">
                          <span className="text-sm">{account.name}</span>
                          <span className="text-xs text-muted-foreground">{account.key}</span>
                        </div>
                      </DropdownMenuItem>
                    ))
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className={`w-full justify-start px-2 pr-2 cursor-pointer`}
              >
                <Avatar className={`h-8 w-8 ${isLeftSidebarOpen ? 'mr-2' : ''}`}>
                  <AvatarImage src="/user-avatar.png" alt="User avatar" />
                  <AvatarFallback className="bg-background dark:bg-border">RP</AvatarFallback>
                </Avatar>
                {isLeftSidebarOpen && <span className="text-muted-foreground">Ryan Porter</span>}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[200px] z-[9999]">
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <Link href="/settings">
                <DropdownMenuItem className="cursor-pointer">
                  <Settings className="mr-2 h-4 w-4 text-navigation-icon" />
                  Settings
                </DropdownMenuItem>
              </Link>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="cursor-pointer" onClick={signOut}>
                <LogOut className="mr-2 h-4 w-4 text-navigation-icon" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <div className="flex items-center justify-between">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DashboardButton
                    variant="ghost"
                    className="pl-4 group"
                    onClick={toggleLeftSidebar}
                  >
                    <PanelLeft className="h-4 w-4 flex-shrink-0 text-navigation-icon" />
                  </DashboardButton>
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
                    <DashboardButton
                      variant="ghost"
                      className="pr-4 group"
                      onClick={toggleTheme}
                    >
                      {theme === "dark" ? (
                        <Moon className="h-4 w-4 flex-shrink-0 text-navigation-icon" />
                      ) : theme === "light" ? (
                        <Sun className="h-4 w-4 flex-shrink-0 text-navigation-icon" />
                      ) : (
                        <Monitor className="h-4 w-4 flex-shrink-0 text-navigation-icon" />
                      )}
                    </DashboardButton>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    Toggle {theme === "dark" ? "Light" : theme === "light" ? "System" : "Dark"} Mode
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        </div>
      </div>
    )
  }

  const RightSidebar = () => {
    return (
      <div className="flex flex-col h-full py-2 bg-frame">
        {rightSidebarState === 'collapsed' && (
          <div className="px-3 py-2">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DashboardButton
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 p-0 group"
                    onClick={toggleRightSidebar}
                  >
                    <MessageSquare className="h-4 w-4 flex-shrink-0 text-navigation-icon" />
                  </DashboardButton>
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
                    <ChatEvaluationCard
                      key="exp1"
                      evaluationId="Evaluation started"
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
                    <ChatEvaluationCard
                      key="exp2"
                      evaluationId="Evaluation completed"
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
                    <ChatEvaluationCard
                      key="exp3"
                      evaluationId="New evaluation"
                      status="running"
                      progress={87}
                      accuracy={88.2}
                      elapsedTime="00:04:35"
                      estimatedTimeRemaining="00:00:40"
                      scorecard="CS3 Services v2"
                      score="Good Call"
                    />,
                    <div key="msg3" className="bg-plexus-chat text-plexus-chat-foreground p-3 rounded-lg max-w-[80%]">
                      Certainly! I'm starting a new evaluation run for the "CS3 Services v2" scorecard on the "Good Call" score.
                    </div>,
                    <div key="user3" className="flex items-start space-x-2 justify-end">
                      <div className="bg-user-chat text-user-chat-foreground p-3 rounded-lg max-w-[80%]">
                        Start a new evaluation run on the "CS3 Services v2" scorecard for the "Good Call" score.
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
              <DashboardButton type="submit" size="icon">
                <Send className="h-4 w-4" />
              </DashboardButton>
            </form>
          </div>
        )}
        <div className="px-3 pt-1 pb-2 flex justify-between items-center">
          {rightSidebarState !== 'collapsed' && (
            <div className="flex space-x-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <DashboardButton
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 p-0 group"
                    >
                      <Mic className="h-4 w-4 flex-shrink-0 text-navigation-icon" />
                    </DashboardButton>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    Dictate Message
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <DashboardButton
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 p-0 group"
                    >
                      <Headphones className="h-4 w-4 flex-shrink-0 text-navigation-icon" />
                    </DashboardButton>
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
                <DashboardButton
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 p-0 ml-auto group"
                  onClick={toggleRightSidebar}
                >
                  <PanelRight className="h-4 w-4 flex-shrink-0 text-navigation-icon" />
                </DashboardButton>
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
    setTheme(theme === "dark" ? "light" : 
            theme === "light" ? "system" : 
            "dark")
  }

  useEffect(() => {
    document.body.classList.add('bg-frame')
    return () => {
      document.body.classList.remove('bg-frame')
    }
  }, [])

  return (
    <div className={`flex flex-col h-screen dashboard-container ${isMobile ? 'bg-background' : 'bg-frame'}`}>
      <MobileHeader 
        toggleLeftSidebar={toggleLeftSidebar}
        toggleRightSidebar={toggleRightSidebar}
        rightSidebarState={rightSidebarState}
      />
      
      <div className={`flex flex-1 min-h-0 relative ${isMobile ? 'bg-background' : 'bg-frame'}`}>
        {/* Mobile sidebar overlay - click outside to close and darken content */}
        {isMobile && isLeftSidebarOpen && (
          <div 
            className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm"
            onClick={toggleLeftSidebar}
          />
        )}
        
        <aside
          className={`
            ${isMobile ? 'fixed top-0 bottom-0 left-0 z-40' : 
              'fixed top-0 bottom-0 left-0 h-full z-10'}
            ${isLeftSidebarOpen ? (isMobile ? 'w-[min(75vw,12rem)]' : 'w-40') : (isMobile ? 'w-12' : 'w-14')}
            transition-all duration-300 ease-in-out overflow-hidden
            ${isMobile && !isLeftSidebarOpen ? 'hidden' : ''}
          `}
        >
          <div className={`
            ${isMobile ? 'h-full w-full bg-frame mobile-sidebar' : 'h-full'}
          `}>
            <LeftSidebar />
          </div>
        </aside>

        <main 
          className={`flex-1 flex flex-col transition-all duration-300 ease-in-out min-h-0 ${isMobile ? 'mobile-main bg-background' : ''}
            ${isMobile ? 'ml-0 mr-0' : (isLeftSidebarOpen ? 'ml-40' : 'ml-14')}
            ${!isMobile && rightSidebarState === 'collapsed' ? 'mr-14' : 
              !isMobile && rightSidebarState === 'normal' ? 'mr-80' : 
              !isMobile && rightSidebarState === 'expanded' ? 'mr-[40%]' : 'mr-0'}
            ${rightSidebarState !== 'collapsed' ? (isMobile ? 'pr-0' : 'pr-2') : 'pr-0'}
            ${isMobile ? 'p-0' : 'p-2'}
          `}
        >
          <div className={`flex-1 flex flex-col bg-background min-h-0 overflow-visible relative ${isMobile ? 'mobile-compact' : 'rounded-lg'}`}>
            {/* Dashboard activation button - bottom center, height of 4 (1rem) */}
            {pathname.startsWith('/lab/') && (
              <button
                onClick={toggleDashboardDrawer}
                className="absolute bottom-0 left-1/3 right-1/3 h-4 z-10 bg-transparent border-none cursor-default opacity-0 hover:opacity-0 focus:outline-none"
                aria-label="Activate dashboard"
                tabIndex={-1}
              />
            )}
            
            {/* Global loading overlay */}
            {isNavigating && (
              <div className={`absolute inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center ${isMobile ? '' : 'rounded-lg'}`}>
                <Spinner size="xl" variant="secondary" />
              </div>
            )}
            <div className="flex-1 min-h-0">
              {children}
            </div>
          </div>
        </main>

        <aside
          className={`
            ${isMobile ? 'fixed top-0 bottom-0 right-0 z-40 bg-background/80 backdrop-blur-sm mobile-hide-right-sidebar' : 
              'fixed top-0 bottom-0 right-0 h-full z-10'}
            ${rightSidebarState === 'collapsed' ? (isMobile ? 'w-0' : 'w-14') :
              rightSidebarState === 'normal' ? (isMobile ? 'w-0' : 'w-80') :
              (isMobile ? 'w-0' : 'w-[40%]')}
            transition-all duration-300 ease-in-out overflow-hidden
          `}
        >
          <div className={`
            ${isMobile ? 'h-full w-full bg-frame' : 'h-full'}
            ${isMobile && rightSidebarState !== 'collapsed' ? 'flex flex-col' : ''}
          `}>
            {isMobile && rightSidebarState !== 'collapsed' && (
              <div className="flex items-center justify-between p-2 border-b">
                <span className="font-semibold">Chat</span>
                <DashboardButton
                  variant="ghost"
                  size="icon"
                  onClick={toggleRightSidebar}
                >
                  <X className="h-5 w-5" />
                </DashboardButton>
              </div>
            )}
            <RightSidebar />
          </div>
        </aside>
      </div>
      
      {/* Dashboard Drawer - only enabled on /lab/ paths */}
      {pathname.startsWith('/lab/') && (
        <DashboardDrawer 
          open={isDashboardDrawerOpen} 
          onOpenChange={setIsDashboardDrawerOpen} 
        />
      )}
    </div>
  )
}

export default DashboardLayout
