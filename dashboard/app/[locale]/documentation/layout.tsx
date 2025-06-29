import DocumentationLayout from './components/documentation-layout'

export default function Layout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <DocumentationLayout>
      {children}
    </DocumentationLayout>
  )
} 