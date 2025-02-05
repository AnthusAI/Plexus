import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { type ButtonProps } from '@/components/ui/button'

interface DocButtonProps extends ButtonProps {
  href: string
  children: React.ReactNode
}

export function DocButton({ href, children, ...props }: DocButtonProps) {
  return (
    <Button
      variant="outline"
      className="group w-full justify-start gap-2"
      asChild
      {...props}
    >
      <Link href={href}>
        {children}
        <span className="ml-auto text-muted-foreground group-hover:translate-x-0.5 transition-transform">
          →
        </span>
      </Link>
    </Button>
  )
} 