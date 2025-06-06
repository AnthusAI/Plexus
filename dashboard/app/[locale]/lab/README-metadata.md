# Lab Routes Metadata Customization

This document explains how to customize the metadata (title, description) for lab routes in the Plexus dashboard.

## Overview

By default, all pages in the Plexus dashboard use the global metadata defined in `dashboard/app/layout.tsx`:

```typescript
export const metadata: Metadata = {
  title: "Plexus - No-Code AI Agents at Scale",
  description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
  // ...
}
```

However, we can override this metadata for specific routes by creating a server component layout file in the route directory.

## How to Customize Metadata for a Lab Route

1. Create a `layout.tsx` file in the route directory (e.g., `dashboard/app/lab/your-route/layout.tsx`)
2. Use the template from `dashboard/app/lab/metadata-template.txt`
3. Customize the title and description for your route

Example:

```typescript
import React from 'react'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: "Your Route Title",
  description: "Your route description goes here.",
  openGraph: {
    title: "Your Route Title",
    description: "Your route description goes here.",
  },
  twitter: {
    title: "Your Route Title",
    description: "Your route description goes here.",
  }
}

export default function YourRouteLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}
```

## Important Notes

1. The layout file must be a server component (no 'use client' directive)
2. The metadata will be applied to the route and all its child routes, unless overridden by a child route
3. The layout function should simply return the children without any additional wrapping

## Currently Customized Routes

The following lab routes have customized metadata:

### Main Routes
- `/lab/activity/` - "Recent Activity" - "Tasks of any kind, with information about their configurations and results."
- `/lab/evaluations/` - "Evaluations" - "Recent evaluations with metrics and results."
- `/lab/scorecards/` - "Scorecards" - "The configurations and past versions for all scorecards and scores."
- `/lab/tasks/` - "Tasks" - "Processing tasks and job status."
- `/lab/datasets/` - "Datasets" - "Manage and explore your datasets for AI evaluation."

### Evaluation Routes
- `/lab/evaluations/[id]` - "Evaluation Results" - "Metrics and score results for one score evaluation."
- `/lab/evaluations/[id]/score-results` - "Score Results" - "Detailed score results for this evaluation."
- `/lab/evaluations/[id]/score-results/[scoreResultId]` - "Score Result Detail" - "Detailed view of an individual score result."

### Scorecard Routes
- `/lab/scorecards/[id]` - "Scorecard" - "Configuration and past version information for one scorecard and its scores."
- `/lab/scorecards/[id]/scores` - "Scorecard Scores" - "All scores for this scorecard with their configurations and versions."
- `/lab/scorecards/[id]/scores/[scoreId]` - "Score Configuration" - "Current champion and version history for the configuration for one scorecard score."

## Adding More Routes

To add metadata for additional routes, copy the template and customize it for each route. 