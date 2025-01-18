import { ReactNode } from 'react'

interface LayoutProps {
  children: ReactNode
}

export const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="min-h-screen bg-background font-sans antialiased">
      <main className="flex-1">{children}</main>
    </div>
  )
}

