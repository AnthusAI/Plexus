interface TocItem {
  id: string
  label: string
  level: number
}

interface TableOfContentsProps {
  items: TocItem[]
}

export function TableOfContents({ items }: TableOfContentsProps) {
  return (
    <nav className="space-y-1">
      {items.map((item) => (
        <a
          key={item.id}
          href={`#${item.id}`}
          className={`block text-sm hover:text-gray-900 ${
            item.level === 2
              ? 'text-gray-900'
              : 'pl-4 text-gray-600'
          }`}
        >
          {item.label}
        </a>
      ))}
    </nav>
  )
} 