import ScorecardContext from './ScorecardContext'

export function EvaluationDashboardSkeleton() {
  return (
    <div className="flex flex-col h-full p-1.5">
      {/* Header with Filter Controls Skeleton */}
      <div className="flex items-center justify-between pb-3">
        <div className="flex items-center space-x-4 flex-1">
          {/* ScorecardContext filter controls skeleton */}
          <div className="flex items-center space-x-3">
            {/* Scorecard filter */}
            <div className="h-10 bg-muted rounded w-48 animate-pulse" />
            {/* Score filter */}
            <div className="h-10 bg-muted rounded w-40 animate-pulse" style={{ animationDelay: '0.1s' }} />
            {/* Time range filter */}
            <div className="h-10 bg-muted rounded w-36 animate-pulse" style={{ animationDelay: '0.2s' }} />
          </div>
        </div>
        {/* Run button skeleton */}
        <div className="h-10 bg-muted rounded w-20 animate-pulse" style={{ animationDelay: '0.3s' }} />
      </div>
      
      {/* Main Content Area */}
      <div className="flex-grow flex flex-col overflow-hidden">
        <div className="flex-1 overflow-auto">
          <div className="@container space-y-3 overflow-visible">
            {/* EvaluationTasksGauges skeleton */}
            <EvaluationTasksGaugesSkeleton />
            
            {/* Evaluations Grid Skeleton */}
            <div className="grid gap-3 grid-cols-1 @[640px]:grid-cols-2">
              {[...Array(4)].map((_, i) => (
                <div 
                  key={i}
                  style={{ animationDelay: `${i * 0.1}s` }}
                  className="animate-pulse"
                >
                  <EvaluationTaskSkeleton />
                </div>
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
            {/* Reports Grid Skeleton - Single column layout */}
            <div className="grid gap-3 grid-cols-1">
              {[...Array(4)].map((_, i) => (
                <div 
                  key={i}
                  style={{ animationDelay: `${i * 0.1}s` }}
                  className="animate-pulse"
                >
                  <ReportTaskSkeleton />
                </div>
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
    <div className="w-full rounded-lg text-card-foreground hover:bg-accent bg-card transition-colors">
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
          <div className="@container space-y-3 overflow-visible">
            {/* TasksGauges skeleton */}
            <TasksGaugesSkeleton />
            
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
              <div key={i} className="bg-card rounded-lg p-4 hover:bg-accent transition-colors">
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
    <div className="@container flex flex-col h-full p-3 overflow-hidden">
      {/* Fixed header */}
      <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
        <div className="@[600px]:flex-grow w-full">
          <ScorecardContext 
            selectedScorecard={null}
            setSelectedScorecard={() => {}}
            selectedScore={null}
            setSelectedScore={() => {}}
            skeletonMode={true}
          />
        </div>
        
        {/* Search Component Skeleton */}
        <div className="flex items-center relative @[600px]:w-auto w-full">
          <div className="relative @[600px]:w-auto w-full">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <div className="h-4 w-4 bg-muted rounded animate-pulse" />
              </div>
              <div className="@[600px]:w-[200px] w-full h-9 pl-10 pr-3 bg-card border-0 rounded-md animate-pulse" />
            </div>
          </div>
        </div>
      </div>
      
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        {/* Content area */}
        <div className="flex flex-1 min-h-0">
          {/* Left panel - grid content */}
          <div className="h-full overflow-auto overflow-x-visible w-full">
            {/* Grid content */}
            <div className="@container space-y-3 overflow-visible">
              {/* ItemsGauges skeleton - this is the key addition */}
              <ItemsGaugesSkeleton />
              
              {/* Items Grid Skeleton */}
              <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 animate-pulse">
                {[...Array(12)].map((_, i) => (
                  <ItemCardSkeleton key={i} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ItemsGauges skeleton component to match the real component structure
function ItemsGaugesSkeleton() {
  return (
    <div className="w-full overflow-visible">
      <div>
        {/* 
          Complex responsive grid layout - MUST match ItemCards grid breakpoints exactly:
          - grid-cols-2 (base, < 500px): gauges stack vertically, chart below full width  
          - @[500px]:grid-cols-3 (≥ 500px): 3 cols, chart takes 1 remaining column
          - @[700px]:grid-cols-4 (≥ 700px): 4 cols, chart takes 2 remaining columns  
          - @[900px]:grid-cols-5 (≥ 900px): 5 cols, chart takes 3 remaining columns
          - @[1100px]:grid-cols-6 (≥ 1100px): 6 cols, chart takes 4 remaining columns
        */}
        <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 items-start">
          
          {/* First gauge - Items per Hour */}
          <div className="bg-card rounded-lg h-48 overflow-visible flex items-center justify-center animate-pulse">
            <div className="w-full h-full flex items-center justify-center">
              <div className="space-y-3 flex flex-col items-center">
                {/* Gauge circle skeleton */}
                <div className="w-24 h-24 bg-muted rounded-full" />
                
                {/* Title skeleton */}
                <div className="text-center space-y-1">
                  <div className="h-4 bg-muted rounded w-20 mx-auto" />
                  <div className="h-3 bg-muted rounded w-16 mx-auto" />
                </div>
              </div>
            </div>
          </div>

          {/* Second gauge - Score Results per Hour */}
          <div className="bg-card rounded-lg h-48 overflow-visible flex items-center justify-center animate-pulse">
            <div className="w-full h-full flex items-center justify-center">
              <div className="space-y-3 flex flex-col items-center">
                {/* Gauge circle skeleton */}
                <div className="w-24 h-24 bg-muted rounded-full" />
                
                {/* Title skeleton */}
                <div className="text-center space-y-1">
                  <div className="h-4 bg-muted rounded w-24 mx-auto" />
                  <div className="h-3 bg-muted rounded w-16 mx-auto" />
                </div>
              </div>
            </div>
          </div>

          {/* 
            Line Chart - Complex responsive behavior matching ItemCards grid exactly:
            - grid-cols-2 (< 500px): spans full width (col-span-2) on second row
            - @[500px]:grid-cols-3 (≥ 500px): spans 1 remaining column (col-span-1)  
            - @[700px]:grid-cols-4 (≥ 700px): spans 2 remaining columns (col-span-2)
            - @[900px]:grid-cols-5 (≥ 900px): spans 3 remaining columns (col-span-3) 
            - @[1100px]:grid-cols-6 (≥ 1100px): spans 4 remaining columns (col-span-4)
          */}
          <div className="col-span-2 @[500px]:col-span-1 @[700px]:col-span-2 @[900px]:col-span-3 @[1100px]:col-span-4 bg-card rounded-lg p-4 h-48 flex flex-col relative animate-pulse">
            {/* Chart title */}
            <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
              <div className="h-4 bg-muted rounded w-32" />
            </div>
            
            <div className="flex flex-col h-full min-w-0">
              {/* Chart area skeleton */}
              <div className="w-full flex-[4] min-h-0 min-w-0 mb-1 @[700px]:flex-[5] @[700px]:mb-0 mt-6">
                <div className="w-full h-full flex items-center justify-center">
                  {/* Chart skeleton - simplified area chart representation */}
                  <div className="w-full h-full relative">
                    {/* Chart background */}
                    <div className="absolute inset-0 bg-muted/20 rounded" />
                    {/* Simulated chart lines */}
                    <div className="absolute bottom-0 left-0 w-full h-1/3 bg-gradient-to-r from-primary/30 to-secondary/30 rounded-b" />
                    <div className="absolute bottom-0 left-0 w-2/3 h-1/2 bg-gradient-to-r from-primary/20 to-secondary/20 rounded-bl" />
                  </div>
                </div>
              </div>
              
              {/* 24-hour totals at the bottom - responsive layout skeleton */}
              <div className="flex justify-between items-end text-sm flex-shrink-0 relative">
                {/* Left metric skeleton */}
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-primary/50 rounded-sm" />
                  <div className="h-4 bg-muted rounded w-12" />
                </div>
                
                {/* Center timestamp skeleton */}
                <div className="absolute left-1/2 bottom-0 transform -translate-x-1/2 mb-1 flex flex-col items-center">
                  <div className="h-2 bg-muted rounded w-16 mb-1" />
                  <div className="h-2 bg-muted rounded w-12" />
                </div>
                
                {/* Right metric skeleton */}
                <div className="flex items-center gap-2">
                  <div className="h-4 bg-muted rounded w-12" />
                  <div className="w-3 h-3 bg-secondary/50 rounded-sm" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// EvaluationTasksGauges skeleton component to match the real component structure (two gauges + chart)
function EvaluationTasksGaugesSkeleton() {
  return (
    <div className="w-full overflow-visible">
      <div>
        {/* Grid layout for two gauges + chart */}
        <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3 items-start">
          
          {/* First gauge - Evaluations per Hour */}
          <div className="bg-card rounded-lg h-48 overflow-visible flex items-center justify-center animate-pulse">
            <div className="w-full h-full flex items-center justify-center">
              <div className="space-y-3 flex flex-col items-center">
                {/* Gauge circle skeleton */}
                <div className="w-24 h-24 bg-muted rounded-full" />
                
                {/* Title skeleton */}
                <div className="text-center space-y-1">
                  <div className="h-4 bg-muted rounded w-20 mx-auto" />
                  <div className="h-3 bg-muted rounded w-16 mx-auto" />
                </div>
              </div>
            </div>
          </div>

          {/* Second gauge - Score Results per Hour */}
          <div className="bg-card rounded-lg h-48 overflow-visible flex items-center justify-center animate-pulse">
            <div className="w-full h-full flex items-center justify-center">
              <div className="space-y-3 flex flex-col items-center">
                {/* Gauge circle skeleton */}
                <div className="w-24 h-24 bg-muted rounded-full" />
                
                {/* Title skeleton */}
                <div className="text-center space-y-1">
                  <div className="h-4 bg-muted rounded w-24 mx-auto" />
                  <div className="h-3 bg-muted rounded w-16 mx-auto" />
                </div>
              </div>
            </div>
          </div>

          {/* Chart component - spans remaining columns */}
          <div className="col-span-2 @[500px]:col-span-1 @[700px]:col-span-2 @[900px]:col-span-3 @[1100px]:col-span-4 bg-card rounded-lg p-4 h-48 flex flex-col relative animate-pulse">
            {/* Chart title */}
            <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
              <div className="h-4 bg-muted rounded w-40" />
            </div>
            
            <div className="flex flex-col h-full min-w-0">
              {/* Chart area skeleton */}
              <div className="w-full flex-[4] min-h-0 min-w-0 mb-1 @[700px]:flex-[5] @[700px]:mb-0 mt-6">
                <div className="w-full h-full flex items-center justify-center">
                  {/* Chart skeleton - simplified area chart representation */}
                  <div className="w-full h-full relative">
                    {/* Chart background */}
                    <div className="absolute inset-0 bg-muted/20 rounded" />
                    {/* Simulated chart lines - primary and secondary colors */}
                    <div className="absolute bottom-0 left-0 w-full h-1/3 bg-gradient-to-r from-primary/30 to-secondary/30 rounded-b" />
                    <div className="absolute bottom-0 left-0 w-2/3 h-1/2 bg-gradient-to-r from-primary/20 to-secondary/20 rounded-bl" />
                  </div>
                </div>
              </div>
              
              {/* 24-hour totals at the bottom - responsive layout skeleton */}
              <div className="flex justify-between items-end text-sm flex-shrink-0 relative">
                {/* Left metric skeleton */}
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-primary/50 rounded-sm" />
                  <div className="h-4 bg-muted rounded w-12" />
                </div>
                
                {/* Center timestamp skeleton */}
                <div className="absolute left-1/2 bottom-0 transform -translate-x-1/2 mb-1 flex flex-col items-center">
                  <div className="h-2 bg-muted rounded w-16 mb-1" />
                  <div className="h-2 bg-muted rounded w-12" />
                </div>
                
                {/* Right metric skeleton */}
                <div className="flex items-center gap-2">
                  <div className="h-4 bg-muted rounded w-12" />
                  <div className="w-3 h-3 bg-secondary/50 rounded-sm" />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// TasksGauges skeleton component to match the real component structure (single gauge + chart)
function TasksGaugesSkeleton() {
  return (
    <div className="w-full overflow-visible">
      <div>
        {/* Flex layout for single gauge + chart */}
        <div className="@container flex gap-3 items-start">
          {/* Single gauge - Tasks per Hour */}
          <div className="bg-card rounded-lg h-48 overflow-visible flex items-center justify-center flex-shrink-0 animate-pulse"
               style={{ width: 'calc((100% - 0.75rem * (2 - 1)) / 2)' }}>
            <div className="w-full h-full flex items-center justify-center">
              <div className="space-y-3 flex flex-col items-center">
                {/* Gauge circle skeleton */}
                <div className="w-24 h-24 bg-muted rounded-full" />
                
                {/* Title skeleton */}
                <div className="text-center space-y-1">
                  <div className="h-4 bg-muted rounded w-20 mx-auto" />
                  <div className="h-3 bg-muted rounded w-16 mx-auto" />
                </div>
              </div>
            </div>
          </div>

          {/* Chart component - greedy */}
          <div className="bg-card rounded-lg p-4 h-48 flex flex-col flex-grow min-w-0 relative animate-pulse">
            {/* Chart title */}
            <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
              <div className="h-4 bg-muted rounded w-32" />
            </div>
            
            <div className="flex flex-col h-full min-w-0">
              {/* Chart area skeleton */}
              <div className="w-full flex-[4] min-h-0 min-w-0 mb-1 @[700px]:flex-[5] @[700px]:mb-0 mt-6">
                <div className="w-full h-full flex items-center justify-center">
                  {/* Chart skeleton - simplified area chart representation */}
                  <div className="w-full h-full relative">
                    {/* Chart background */}
                    <div className="absolute inset-0 bg-muted/20 rounded" />
                    {/* Simulated chart lines */}
                    <div className="absolute bottom-0 left-0 w-full h-1/3 bg-gradient-to-r from-chart-1/30 to-chart-1/30 rounded-b" />
                    <div className="absolute bottom-0 left-0 w-2/3 h-1/2 bg-gradient-to-r from-chart-1/20 to-chart-1/20 rounded-bl" />
                  </div>
                </div>
              </div>
              
              {/* Bottom area with timestamp */}
              <div className="flex justify-center items-end text-sm flex-shrink-0 relative">
                {/* Center timestamp skeleton */}
                <div className="flex flex-col items-center">
                  <div className="h-2 bg-muted rounded w-16 mb-1" />
                  <div className="h-2 bg-muted rounded w-12" />
                </div>
              </div>
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
    <div className="w-full rounded-lg text-card-foreground hover:bg-accent bg-card transition-colors">
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
          <div className="pt-1">
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