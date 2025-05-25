export function EvaluationDashboardSkeleton() {
  return (
    <div className="flex flex-col h-full p-1.5 animate-pulse">
      {/* Header with Filter Controls Skeleton */}
      <div className="flex items-center justify-between pb-3">
        <div className="flex items-center space-x-4 flex-1">
          {/* ScorecardContext filter controls skeleton */}
          <div className="flex items-center space-x-3">
            {/* Scorecard filter */}
            <div className="h-10 bg-muted rounded w-48" />
            {/* Score filter */}
            <div className="h-10 bg-muted rounded w-40" />
            {/* Time range filter */}
            <div className="h-10 bg-muted rounded w-36" />
          </div>
        </div>
        {/* Run button skeleton */}
        <div className="h-10 bg-muted rounded w-20" />
      </div>
      
      {/* Main Content Area */}
      <div className="flex-grow flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          <div className="@container h-full">
            {/* Evaluations Grid Skeleton */}
            <div className="grid gap-3 grid-cols-1 @[640px]:grid-cols-2">
              {[...Array(4)].map((_, i) => (
                <EvaluationTaskSkeleton key={i} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Separate EvaluationTask skeleton component for reusability
function EvaluationTaskSkeleton() {
  return (
    <div className="w-full rounded-lg text-card-foreground hover:bg-accent/50 bg-card">
      <div className="p-4 w-full">
        {/* Task Header */}
        <div className="flex justify-between items-start mb-4">
          <div className="flex gap-3 flex-1">
            {/* Task Icon */}
            <div className="h-9 w-9 bg-muted rounded flex-shrink-0" />
            
            {/* Task Info */}
            <div className="space-y-2 flex-1">
              {/* Task Title */}
              <div className="h-5 bg-muted rounded w-3/4" />
              
              {/* Scorecard and Score info */}
              <div className="flex gap-2">
                <div className="h-4 bg-muted rounded w-24" />
                <div className="h-4 bg-muted rounded w-20" />
              </div>
              
              {/* Timestamp */}
              <div className="h-3 bg-muted rounded w-16" />
            </div>
          </div>
          
          {/* Control Buttons */}
          <div className="flex gap-2">
            <div className="h-8 w-8 bg-muted rounded" />
            <div className="h-8 w-8 bg-muted rounded" />
          </div>
        </div>
        
        {/* Bottom Progress Bars Section */}
        <div className="space-y-3">
          {/* Segmented Progress Bar (Task Stages) */}
          <div className="h-3 bg-muted rounded w-full" />
          
          {/* Regular Progress Bar (Items Processed) */}
          <div className="h-3 bg-muted rounded w-full" />
          
          {/* Accuracy Bar (Evaluation Results) */}
          <div className="h-3 bg-muted rounded w-full" />
        </div>
      </div>
    </div>
  );
}

export function ReportsDashboardSkeleton() {
  return (
    <div className="flex flex-col h-full p-1.5 animate-pulse">
      {/* Header with Filter Controls Skeleton */}
      <div className="flex items-center justify-between pb-3">
        <div className="flex items-center space-x-4 flex-1">
          {/* ScorecardContext filter controls skeleton */}
          <div className="flex items-center space-x-3">
            {/* Scorecard filter */}
            <div className="h-10 bg-muted rounded w-48" />
            {/* Score filter */}
            <div className="h-10 bg-muted rounded w-40" />
            {/* Time range filter */}
            <div className="h-10 bg-muted rounded w-36" />
          </div>
        </div>
        {/* Run Report button skeleton */}
        <div className="h-10 bg-muted rounded w-24" />
      </div>
      
      {/* Main Content Area */}
      <div className="flex-grow flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          <div className="@container h-full">
            {/* Reports Grid Skeleton */}
            <div className="grid gap-3 grid-cols-1 @[640px]:grid-cols-2">
              {[...Array(4)].map((_, i) => (
                <ReportTaskSkeleton key={i} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Report Task skeleton component (similar to scorecard cards)
function ReportTaskSkeleton() {
  return (
    <div className="w-full rounded-lg text-card-foreground hover:bg-accent/50 bg-card">
      <div className="p-4 w-full">
        <div className="flex justify-between items-start">
          <div className="space-y-2 min-h-[4.5rem] flex-1">
            {/* Report Name */}
            <div className="h-6 bg-muted rounded w-3/4" />
            {/* Description */}
            <div className="h-4 bg-muted rounded w-full" />
            {/* Created/Updated timestamp */}
            <div className="h-3 bg-muted rounded w-16" />
          </div>
          {/* Report/Task icon placeholder */}
          <div className="h-6 w-6 bg-muted rounded ml-4" />
        </div>
      </div>
    </div>
  );
}

export function ActivityDashboardSkeleton() {
  return (
    <div className="flex flex-col h-full p-1.5 animate-pulse">
      {/* Header with Filter Controls Skeleton */}
      <div className="flex items-center justify-between pb-3">
        <div className="flex items-center space-x-4 flex-1">
          {/* ScorecardContext filter controls skeleton */}
          <div className="flex items-center space-x-3">
            {/* Scorecard filter */}
            <div className="h-10 bg-muted rounded w-48" />
            {/* Score filter */}
            <div className="h-10 bg-muted rounded w-40" />
            {/* Time range filter */}
            <div className="h-10 bg-muted rounded w-36" />
          </div>
        </div>
        {/* Run button skeleton */}
        <div className="h-10 bg-muted rounded w-20" />
      </div>
      
      {/* Main Content Area */}
      <div className="flex-grow flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          <div className="@container h-full">
            {/* Activity Grid Skeleton (mix of evaluations and tasks) */}
            <div className="grid gap-3 grid-cols-1 @[640px]:grid-cols-2">
              {[...Array(4)].map((_, i) => (
                <EvaluationTaskSkeleton key={i} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ScorecardDashboardSkeleton() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 space-y-3 p-1.5 w-full animate-pulse">
        {/* New Scorecard Button Skeleton */}
        <div className="flex justify-end">
          <div className="h-10 bg-muted rounded w-32" />
        </div>
        
        {/* Grid Container */}
        <div className="@container">
          <div className="grid grid-cols-1 @[400px]:grid-cols-1 @[600px]:grid-cols-2 @[900px]:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-card rounded-lg p-4 hover:bg-accent/50 transition-colors">
                <div className="flex justify-between items-start">
                  <div className="space-y-2 min-h-[4.5rem] flex-1">
                    {/* Scorecard Name */}
                    <div className="h-6 bg-muted rounded w-3/4" />
                    {/* Description */}
                    <div className="h-4 bg-muted rounded w-full" />
                  </div>
                  {/* Icon placeholder */}
                  <div className="h-6 w-6 bg-muted rounded ml-4" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ItemsDashboardSkeleton() {
  return (
    <div className="flex flex-col h-full p-1.5 animate-pulse">
      {/* Header with Filter Controls Skeleton */}
      <div className="flex items-center justify-between pb-3">
        <div className="flex items-center space-x-4 flex-1">
          {/* ScorecardContext filter controls skeleton */}
          <div className="flex items-center space-x-3">
            {/* Scorecard filter */}
            <div className="h-10 bg-muted rounded w-48" />
            {/* Score filter */}
            <div className="h-10 bg-muted rounded w-40" />
            {/* Time range filter */}
            <div className="h-10 bg-muted rounded w-36" />
          </div>
        </div>
      </div>
      
      {/* Main Content Area */}
      <div className="flex-grow flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          <div className="@container h-full">
            {/* Items Grid Skeleton */}
            <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3">
              {[...Array(12)].map((_, i) => (
                <ItemCardSkeleton key={i} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Separate ItemCard skeleton component for reusability
export function ItemCardSkeleton() {
  return (
    <div className="w-full rounded-lg text-card-foreground hover:bg-accent/50 bg-card">
      <div className="p-3 w-full">
        <div className="space-y-2">
          {/* Top section with scorecard name and timestamp */}
          <div className="flex justify-between items-start">
            <div className="h-4 bg-muted rounded w-20" />
            <div className="h-3 bg-muted rounded w-12" />
          </div>
          
          {/* Main content area */}
          <div className="space-y-2">
            {/* Score/Evaluation info */}
            <div className="space-y-1">
              <div className="h-4 bg-muted rounded w-3/4" />
              <div className="h-3 bg-muted rounded w-1/2" />
            </div>
            
            {/* Badge/Status area */}
            <div className="flex gap-1">
              <div className="h-5 bg-muted rounded-full w-16" />
              <div className="h-5 bg-muted rounded-full w-12" />
            </div>
          </div>
          
          {/* Bottom metrics area */}
          <div className="pt-1 border-t border-border/50">
            <div className="flex justify-between items-center">
              <div className="flex space-x-2">
                <div className="h-3 bg-muted rounded w-8" />
                <div className="h-3 bg-muted rounded w-10" />
              </div>
              <div className="h-3 bg-muted rounded w-12" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 