export function WorkflowConnection({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width="100%"
      height="100%"
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="none"
    >
      <path d="M50 0 L50 25 Q50 50 75 50 L100 50" stroke="currentColor" strokeWidth="2" />
      <path d="M50 25 Q50 50 25 50 L0 50" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

