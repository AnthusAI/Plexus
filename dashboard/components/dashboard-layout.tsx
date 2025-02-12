"use client"

import * as React from "react"
import { useState, useEffect, useRef } from "react"
import { Activity, StickyNote, FileBarChart, FlaskConical, ListTodo, LogOut, Menu, PanelLeft, PanelRight, Settings, Sparkles, Siren, Database, Sun, Moon, Send, Mic, Headphones, MessageCircleMore, MessageSquare, Inbox, X, ArrowLeftRight, Layers3, Monitor } from "lucide-react"
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

import SquareLogo, { LogoVariant } from './logo-square'
import { useSidebar } from "@/app/contexts/SidebarContext"
import { useAccount } from "@/app/contexts/AccountContext"

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
  <div className="hidden max-lg:flex items-center justify-between p-1 px-2 bg-background">
    <DashboardButton
      variant="ghost"
      size="icon"
      onClick={toggleLeftSidebar}
      className="lg:hidden"
    >
      <Menu className="h-5 w-5" />
    </DashboardButton>
    
    <Link href="/" className="flex items-center">
      <SquareLogo variant={LogoVariant.Narrow} />
    </Link>

    <DashboardButton
      variant="ghost"
      size="icon"
      onClick={toggleRightSidebar}
      className="lg:hidden"
    >
      <MessageSquare className="h-5 w-5" />
    </DashboardButton>
  </div>
)

const client = generateClient<Schema>()

type Account = Schema['Account']['type']

export const menuItems = [
  { name: "Activity", icon: Activity, path: "/activity" },
  { name: "Scorecards", icon: ListTodo, path: "/scorecards" },
  { name: "Datasets", icon: Database, path: "/datasets" },
  { name: "Evaluations", icon: FlaskConical, path: "/evaluations" },
  { name: "Items", icon: StickyNote, path: "/items" },
  { name: "Batches", icon: Layers3, path: "/batches" },
  { name: "Feedback", icon: MessageCircleMore, path: "/feedback-queues" },
  { name: "Reports", icon: FileBarChart, path: "/reports" },
  { name: "Alerts", icon: Siren, path: "/alerts" },
]

const DashboardLayout = ({ children, signOut }: { children: React.ReactNode; signOut: () => Promise<void> }) => {
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true)
  const { rightSidebarState, setRightSidebarState } = useSidebar()
  const { theme, setTheme } = useTheme()
  const isDesktop = useMediaQuery("(min-width: 1024px)")
  const isMobile = useMediaQuery("(max-width: 1023px)")
  const { accounts, selectedAccount, isLoadingAccounts, visibleMenuItems, setSelectedAccount } = useAccount()

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

  const pathname = usePathname()

  const LeftSidebar = () => {
    return (
      <div className={`flex flex-col h-full py-2 bg-frame ${isMobile ? 'pr-3' : 'pr-2'}`}>
        <div className={`mb-4 ${isLeftSidebarOpen ? 'pl-2' : ''}`}>
          <Link href="/" className={`block relative ${isLeftSidebarOpen ? 'w-full max-w-md' : 'w-12 pl-2'}`}>
            <div className="absolute -inset-1 bg-gradient-to-r from-secondary to-primary rounded-md blur-sm opacity-50"></div>
            <div className="relative">
              {isLeftSidebarOpen ? (
                <SquareLogo variant={LogoVariant.Wide} />
              ) : (
                <SquareLogo variant={LogoVariant.Narrow} />
              )}
            </div>
          </Link>
        </div>

        <ScrollArea className="flex-grow overflow-y-auto">
          <div className={`${isLeftSidebarOpen ? 'pl-2' : 'px-3'} ${isMobile ? 'space-y-2' : 'space-y-1'}`}>
            {visibleMenuItems.map((item) => (
              <TooltipProvider key={item.name}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link href={item.path} passHref>
                      <DashboardButton
                        variant={
                          (pathname === item.path || 
                          (item.name === "Feedback" && (pathname === "/feedback-queues" || pathname.startsWith("/feedback"))) ||
                          (item.name === "Scorecards" && pathname.startsWith("/scorecards")))
                            ? "secondary"
                            : "ghost"
                        }
                        className={`w-full justify-start group !rounded-[4px] ${
                          (pathname === item.path || 
                          (item.name === "Feedback" && (pathname === "/feedback-queues" || pathname.startsWith("/feedback"))) ||
                          (item.name === "Scorecards" && pathname.startsWith("/scorecards")))
                            ? "bg-secondary text-secondary-foreground"
                            : ""
                        } ${isLeftSidebarOpen ? '' : 'px-2'} ${
                          isMobile ? 'py-3' : ''
                        }`}
                      >
                        <item.icon className={`h-4 w-4 flex-shrink-0 ${
                          (pathname === item.path || 
                          (item.name === "Feedback" && (pathname === "/feedback-queues" || pathname.startsWith("/feedback"))) ||
                          (item.name === "Scorecards" && pathname.startsWith("/scorecards")))
                            ? "text-secondary-foreground"
                            : "text-secondary group-hover:text-accent-foreground"
                        }`} />
                        {isLeftSidebarOpen && (
                          <span className="ml-3">{item.name}</span>
                        )}
                      </DashboardButton>
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    {item.name}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ))}
          </div>
        </ScrollArea>

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
                    {selectedAccount?.name?.split(' ').map(word => word[0]).join('') || 'AC'}
                  </AvatarFallback>
                </Avatar>
                {isLeftSidebarOpen && <span>{selectedAccount?.name || 'Select Account'}</span>}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-[200px]">
              <Link href="/settings">
                <DropdownMenuItem className="cursor-pointer">
                  <Settings className="mr-2 h-4 w-4" />
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
                <DropdownMenuContent side="right" align="start" className="w-[200px]">
                  {isLoadingAccounts ? (
                    <DropdownMenuItem>Loading accounts...</DropdownMenuItem>
                  ) : accounts.length === 0 ? (
                    <DropdownMenuItem>No accounts found</DropdownMenuItem>
                  ) : (
                    accounts.map((account) => (
                      <DropdownMenuItem 
                        key={account.id} 
                        className="cursor-pointer"
                        onClick={() => setSelectedAccount(account)}
                      >
                        <Avatar className="h-8 w-8 mr-2">
                          <AvatarImage 
                            src={`/avatar-${account.key}.png`} 
                            alt={account.name} 
                          />
                          <AvatarFallback className="bg-frame dark:bg-border">
                            {account.name.split(' ').map(word => word[0]).join('')}
                          </AvatarFallback>
                        </Avatar>
                        <span>{account.name}</span>
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
                {isLeftSidebarOpen && <span>Ryan Porter</span>}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-[200px]">
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <Link href="/settings">
                <DropdownMenuItem className="cursor-pointer">
                  <Settings className="mr-2 h-4 w-4" />
                  Settings
                </DropdownMenuItem>
              </Link>
              <DropdownMenuSeparator />
              <DropdownMenuItem className="cursor-pointer" onClick={signOut}>
                <LogOut className="mr-2 h-4 w-4" />
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
                    <PanelLeft className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
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
                        <Moon className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                      ) : theme === "light" ? (
                        <Sun className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                      ) : (
                        <Monitor className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
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
                    <MessageSquare className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
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
                      <Mic className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
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
                      <Headphones className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
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
                  <PanelRight className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
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
    <div className="flex flex-col h-screen bg-frame">
      <MobileHeader 
        toggleLeftSidebar={toggleLeftSidebar}
        toggleRightSidebar={toggleRightSidebar}
        rightSidebarState={rightSidebarState}
      />
      
      <div className="flex flex-1 overflow-hidden bg-frame">
        <aside
          className={`
            ${isMobile ? 'fixed top-[40px] bottom-0 left-0 z-50 bg-background/80 backdrop-blur-sm' : 
              'fixed top-0 bottom-0 left-0 h-full'}
            ${isLeftSidebarOpen ? 'w-40' : 'w-14'}
            transition-all duration-300 ease-in-out overflow-hidden
            ${isMobile && !isLeftSidebarOpen ? 'hidden' : ''}
          `}
          onClick={() => {
            console.log('Right sidebar clicked:', {
              rightSidebarState,
              isMobile,
              width: rightSidebarState === 'collapsed' ? 
                (isMobile ? '0' : '14') : 
                (rightSidebarState === 'normal' ? '80' : 'full')
            });
          }}
        >
          <div className={`
            ${isMobile ? 'h-full w-40 bg-frame' : 'h-full'}
          `}>
            <LeftSidebar />
          </div>
        </aside>

        <main 
          className={`flex-1 flex flex-col transition-all duration-300 ease-in-out
            ${isMobile ? 'ml-0' : (isLeftSidebarOpen ? 'ml-40' : 'ml-14')}
            ${isMobile && rightSidebarState === 'collapsed' ? 'mr-0' : 
              rightSidebarState === 'normal' ? (isMobile ? 'mr-0' : 'mr-80') : 
              rightSidebarState === 'expanded' ? (isMobile ? 'mr-0' : 'mr-[40%]') : 
              (isMobile ? 'mr-0' : 'mr-14')}
            ${rightSidebarState !== 'collapsed' ? 'pr-2' : 'pr-0'}
            ${isMobile ? '' : 'py-2'}
          `}
        >
          <div className="flex-1 flex flex-col bg-background rounded-lg overflow-hidden">
            <div className="flex-1 overflow-y-auto">
              <div className={`h-full pr-2 pb-2 pl-2 ${isMobile ? '' : 'pt-2'}`}>
                {children}
              </div>
            </div>
          </div>
        </main>

        <aside
          className={`
            ${isMobile ? 'fixed top-[40px] bottom-0 right-0 z-50 bg-background/80 backdrop-blur-sm' : 
              'fixed top-0 bottom-0 right-0 h-full'}
            ${rightSidebarState === 'collapsed' ? (isMobile ? 'w-0' : 'w-14') :
              rightSidebarState === 'normal' ? 'w-80' :
              (isMobile ? 'w-full' : 'w-[40%]')}
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
    </div>
  )
}

export default DashboardLayout
