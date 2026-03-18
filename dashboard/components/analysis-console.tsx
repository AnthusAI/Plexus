export default function AnalysisConsole() {
  return (
    <div className="px-6 pt-0 pb-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Analysis</h1>
        <p className="text-muted-foreground">
          Investigate patterns, outcomes, and root causes across your account data.
        </p>
      </div>

      <section
        aria-label="Analysis console workspace"
        className="min-h-[24rem] rounded-lg border bg-card"
      />
    </div>
  )
}
