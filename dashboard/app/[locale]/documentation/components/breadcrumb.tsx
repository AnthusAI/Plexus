import Link from 'next/link'

interface BreadcrumbProps {
  items: Array<{
    label: string
    href?: string
  }>
}

export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav className="mb-6 flex" aria-label="Breadcrumb">
      <ol className="flex items-center space-x-2">
        <li>
          <Link
            href="/documentation"
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Documentation
          </Link>
        </li>
        
        {items.map((item, index) => (
          <li key={item.label} className="flex items-center">
            <svg
              className="h-5 w-5 text-gray-400"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
            {item.href ? (
              <Link
                href={item.href}
                className="ml-2 text-sm text-gray-500 hover:text-gray-700"
              >
                {item.label}
              </Link>
            ) : (
              <span className="ml-2 text-sm text-gray-900">{item.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
} 