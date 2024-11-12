export function ExperimentDashboardSkeleton() {
  return (
    <div className="space-y-4 h-full flex flex-col animate-pulse">
      <div className="h-10 bg-muted rounded w-1/3" />
      <div className="flex-grow flex flex-col">
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-muted rounded" />
          ))}
        </div>
      </div>
    </div>
  );
} 