"use client"

import * as React from "react"
import { useState, useEffect } from "react"
import { Menu, PanelLeft, Sun, Moon, Monitor } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"

import { Button, type ButtonProps } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import SquareLogo, { LogoVariant } from '@/components/logo-square'

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

const DocButton = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, ...props }, ref) => (
    <Button ref={ref} className={`!rounded-[6px] ${className}`} {...props} />
  )
)
DocButton.displayName = "DocButton"

const MobileHeader = ({ 
  toggleLeftSidebar,
  toggleRightSidebar,
}: { 
  toggleLeftSidebar: () => void;
  toggleRightSidebar: () => void;
}) => (
  <div className="hidden max-lg:flex items-center justify-between p-1 px-2 bg-background">
    <DocButton
      variant="ghost"
      size="icon"
      onClick={toggleLeftSidebar}
      className="lg:hidden"
    >
      <Menu className="h-5 w-5" />
    </DocButton>
    
    <Link href="/" className="flex items-center">
      <SquareLogo variant={LogoVariant.Narrow} />
    </Link>

    <DocButton
      variant="ghost"
      size="icon"
      onClick={toggleRightSidebar}
      className="lg:hidden"
    >
      <Menu className="h-5 w-5" />
    </DocButton>
  </div>
)

interface DocSidebarItem {
  name: string;
  href: string;
  items?: Array<{
    name: string;
    href: string;
  }>;
}

const docSections: DocSidebarItem[] = [
  {
    name: "Introduction",
    href: "/documentation",
  },
  {
    name: "Concepts",
    href: "/documentation/concepts",
    items: [
      { name: "Items", href: "/documentation/concepts/items" },
      { name: "Sources", href: "/documentation/concepts/sources" },
      { name: "Scores", href: "/documentation/concepts/scores" },
      { name: "Scorecards", href: "/documentation/concepts/scorecards" },
      { name: "Score Results", href: "/documentation/concepts/score-results" },
      { name: "Evaluations", href: "/documentation/concepts/evaluations" },
      { name: "Evaluation Metrics", href: "/documentation/concepts/evaluation-metrics" },
      { name: "Tasks", href: "/documentation/concepts/tasks" },
      { name: "Reports", href: "/documentation/concepts/reports" },
    ],
  },
  {
    name: "Methods",
    href: "/documentation/methods",
    items: [
      { name: "Add/Edit a Source", href: "/documentation/methods/add-edit-source" },
      { name: "Profile a Source", href: "/documentation/methods/profile-source" },
      { name: "Add/Edit a Scorecard", href: "/documentation/methods/add-edit-scorecard" },
      { name: "Add/Edit a Score", href: "/documentation/methods/add-edit-score" },
      { name: "Evaluate a Score", href: "/documentation/methods/evaluate-score" },
      { name: "Monitor Tasks", href: "/documentation/methods/monitor-tasks" },
    ],
  },
  {
    name: "Advanced",
    href: "/documentation/advanced",
    items: [
      { name: "plexus CLI Tool", href: "/documentation/advanced/cli" },
      { name: "Worker Nodes", href: "/documentation/advanced/worker-nodes" },
      { name: "Python SDK Reference", href: "/documentation/advanced/sdk" },
      { name: "MCP Server", href: "/documentation/advanced/mcp-server" },
    ],
  },
]

interface DocumentationLayoutProps {
  children: React.ReactNode;
  tableOfContents?: Array<{
    id: string;
    level: number;
    text: string;
  }>;
}

export default function DocumentationLayout({ children, tableOfContents }: DocumentationLayoutProps) {
  const [isLeftSidebarOpen, setIsLeftSidebarOpen] = useState(true)
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true)
  const { theme, setTheme } = useTheme()
  const isDesktop = useMediaQuery("(min-width: 1024px)")
  const isMobile = useMediaQuery("(max-width: 1023px)")
  const pathname = usePathname()

  useEffect(() => {    
    if (isDesktop) {
      setIsLeftSidebarOpen(true)
      setIsRightSidebarOpen(true)
    } else if (isMobile) {
      setIsLeftSidebarOpen(false)
      setIsRightSidebarOpen(false)
    }
  }, [isDesktop, isMobile])

  const toggleLeftSidebar = () => setIsLeftSidebarOpen(!isLeftSidebarOpen)
  const toggleRightSidebar = () => setIsRightSidebarOpen(!isRightSidebarOpen)

  const LeftSidebar = () => {
    return (
      <div className="flex flex-col h-full py-2 bg-muted">
        <div className={`mb-4 ${isLeftSidebarOpen ? 'pl-2' : ''}`}>
          <Link href="/" className={`block relative ${isLeftSidebarOpen ? 'w-[140px] ml-4' : 'w-12 pl-2'}`}>
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
            {docSections.map((section) => (
              <div key={section.name} className="mb-4">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link href={section.href}>
                        <DocButton
                          variant={pathname === section.href ? "secondary" : "ghost"}
                          className={`w-full justify-start group !rounded-[4px] ${
                            isLeftSidebarOpen ? '' : 'px-2'
                          }`}
                        >
                          {section.name === "plexus CLI Tool" ? (
                            <code className="text-sm">{section.name}</code>
                          ) : (
                            section.name
                          )}
                        </DocButton>
                      </Link>
                    </TooltipTrigger>
                    {!isLeftSidebarOpen && (
                      <TooltipContent side="right">
                        {section.name}
                      </TooltipContent>
                    )}
                  </Tooltip>
                </TooltipProvider>

                {isLeftSidebarOpen && section.items && (
                  <div className="ml-4 mt-1 space-y-1">
                    {section.items.map((item) => (
                      <Link key={item.href} href={item.href}>
                        <DocButton
                          variant={pathname === item.href ? "secondary" : "ghost"}
                          className="w-full justify-start text-sm"
                        >
                          {item.name}
                        </DocButton>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </ScrollArea>

        <div className="mt-auto pl-2 space-y-2 py-2">
          <div className="flex items-center justify-between">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DocButton
                    variant="ghost"
                    className="pl-4 group"
                    onClick={toggleLeftSidebar}
                  >
                    <PanelLeft className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                  </DocButton>
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
                    <DocButton
                      variant="ghost"
                      className="pr-4 group"
                      onClick={() => {
                        setTheme(theme === "dark" ? "light" : 
                                theme === "light" ? "system" : 
                                "dark")
                      }}
                    >
                      {theme === "dark" ? (
                        <Moon className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                      ) : theme === "light" ? (
                        <Sun className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                      ) : (
                        <Monitor className="h-4 w-4 flex-shrink-0 text-secondary group-hover:text-accent-foreground" />
                      )}
                    </DocButton>
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
    if (!tableOfContents?.length) return null

    return (
      <div className="flex flex-col h-full py-2 bg-muted">
        <div className="px-4">
          <h4 className="mb-3 text-sm font-semibold text-foreground">On this page</h4>
          <ScrollArea className="h-[calc(100vh-6rem)]">
            <nav className="space-y-1">
              {tableOfContents.map((item) => (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className={`block text-sm hover:text-accent ${
                    item.level === 1 ? 'font-medium' :
                    item.level === 2 ? 'pl-4' :
                    'pl-6'
                  } ${
                    item.level === 1 ? 'text-foreground' : 'text-muted-foreground'
                  }`}
                >
                  {item.text}
                </a>
              ))}
            </nav>
          </ScrollArea>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-muted">
      <MobileHeader 
        toggleLeftSidebar={toggleLeftSidebar}
        toggleRightSidebar={toggleRightSidebar}
      />
      
      <div className="flex flex-1 overflow-hidden bg-muted">
        <aside
          className={`
            ${isMobile ? 'fixed top-[40px] bottom-0 left-0 z-50 bg-background/80 backdrop-blur-sm' : 
              'fixed top-0 bottom-0 left-0 h-full'}
            ${isLeftSidebarOpen ? 'w-64' : 'w-14'}
            transition-all duration-300 ease-in-out overflow-hidden
            ${isMobile && !isLeftSidebarOpen ? 'hidden' : ''}
          `}
        >
          <div className={`
            ${isMobile ? 'h-full w-64 bg-muted' : 'h-full'}
          `}>
            <LeftSidebar />
          </div>
        </aside>

        <main 
          className={`flex-1 flex flex-col transition-all duration-300 ease-in-out
            ${isMobile ? 'ml-0' : (isLeftSidebarOpen ? 'ml-64' : 'ml-14')}
            ${isMobile ? 'mr-0' : (isRightSidebarOpen && tableOfContents?.length ? 'mr-64' : 'mr-0')}
            ${isMobile ? '' : 'py-2'}
          `}
        >
          <div className="flex-1 flex flex-col bg-background rounded-lg overflow-hidden">
            <div className="flex-1 overflow-y-auto">
              <div className={`h-full pr-2 pb-2 pl-2 ${isMobile ? '' : 'pt-2'}`}>
                <div className="prose prose-gray dark:prose-invert max-w-none">
                  {children}
                </div>
              </div>
            </div>
          </div>
        </main>

        {tableOfContents?.length && (
          <aside
            className={`
              ${isMobile ? 'fixed top-[40px] bottom-0 right-0 z-50 bg-background/80 backdrop-blur-sm' : 
                'fixed top-0 bottom-0 right-0 h-full'}
              ${isRightSidebarOpen ? 'w-64' : 'w-0'}
              transition-all duration-300 ease-in-out overflow-hidden
            `}
          >
            <div className={`
              ${isMobile ? 'h-full w-64 bg-muted' : 'h-full'}
            `}>
              <RightSidebar />
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}