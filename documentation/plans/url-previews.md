# URL Preview Customization Plan

## Overview
This document outlines the implementation plan for customizing URL previews when Plexus links are shared on platforms like Skype, Discord, Slack, Facebook, and Twitter. The goal is to provide rich, informative previews that accurately represent the content being shared, enhancing the user experience and increasing engagement.

## Background

### Technical Implementation
URL previews are generated using metadata tags in the HTML of a webpage. The most common standards are:

1. **Open Graph Protocol (OG)**: Developed by Facebook, now widely adopted across platforms
2. **Twitter Cards**: Twitter-specific metadata for customizing Twitter previews
3. **Schema.org**: Structured data format that can influence how search engines display results

### Current Implementation in Plexus
Currently, Plexus has basic metadata implemented in the root layout file (`dashboard/app/layout.tsx`):

```tsx
export const metadata: Metadata = {
  title: "Plexus - No-Code AI Agents at Scale",
  description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
  openGraph: {
    title: "Plexus - No-Code AI Agents at Scale",
    description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
    url: "https://plexus.anth.us",
    siteName: "Plexus",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Plexus - No-Code AI Agents at Scale"
      }
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Plexus - No-Code AI Agents at Scale",
    description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
    creator: "@Anthus_AI",
    images: ["/og-image.png"],
  }
};
```

This implementation provides a generic preview for all Plexus URLs, but does not offer dynamic, content-specific previews for individual routes.

### Terminology and Route Definitions
For clarity, we establish the following vocabulary for this document:

- **Evaluation Share URLs**: Routes following the pattern `/evaluations/[id]` - These are public-facing URLs for sharing evaluation results with users who may not have Plexus accounts.
- **Lab Evaluation URLs**: Routes following the pattern `/lab/evaluations/...` - These are internal dashboard routes for authenticated users working within the Plexus platform.

### Relevant Files
The following files are relevant to implementing dynamic URL previews:

1. **Root Layout**: `dashboard/app/layout.tsx` - Contains the default metadata
2. **Client Layout**: `dashboard/app/client-layout.tsx` - Handles authentication and routing
3. **Evaluation Share Routes**: 
   - `dashboard/app/evaluations/[id]/page.tsx` - Dynamic route for public evaluation sharing
   - `dashboard/app/evaluations/[id]/layout.tsx` - Layout for public evaluation pages
4. **Lab Evaluation Routes**: Various routes under `dashboard/app/lab/evaluations/` for internal evaluation management

## Updated Approach: Text-Only Evaluation Summaries

### Evaluation Summary Format
For evaluation share URLs, we will implement a text-only approach that focuses on providing a concise summary of the evaluation results in the description field. The format will be:

```
"Evaluation results for {scorecard name} - {score name}: {accuracy percentage}% accuracy, {precision percentage}% precision, ..."
```

### Dynamic Metrics Extraction
Since metrics are not predefined and come from JSON data in the Evaluation records, we will:

1. Create a reusable utility function `formatEvaluationSummary` that:
   - Takes an Evaluation record as input
   - Extracts the scorecard name, score name, and metrics from the JSON data
   - Formats the metrics into a human-readable string
   - Returns a complete summary string

2. This utility function will be:
   - Placed in a shared utilities directory for reuse across the codebase
   - Used for both URL preview generation and other use cases requiring evaluation summaries
   - Designed to handle various metric formats and missing data gracefully

## Implementation Strategy

### 1. Dynamic Metadata Generation
We will implement dynamic metadata generation using Next.js's `generateMetadata` function for routes that need customized previews, with a focus on text-based descriptions for evaluations.

### 2. Priority Routes for Implementation

#### Evaluation Share URLs (Priority)
For `/evaluations/[id]` routes, we will:
- Generate dynamic titles based on evaluation name/ID
- Create text-only descriptions using the `formatEvaluationSummary` utility function
- Use a standard Plexus logo image rather than dynamic images
- Include evaluation creation date in the metadata

#### Lab Evaluation URLs (Secondary)
For `/lab/evaluations/...` routes, we will:
- Generate titles that reflect the specific evaluation context within the lab
- Create descriptions using the same `formatEvaluationSummary` utility function
- Use the standard Plexus logo image
- Include metadata about the evaluation context

### 3. Metadata Policies by Route Type

| Route Type | Title Format | Description Format | Image Strategy | Additional Metadata |
|------------|--------------|-------------------|----------------|---------------------|
| Evaluation Share URL | "Evaluation: {name}" | "Evaluation results for {scorecard} - {score}: {metric1}%, {metric2}%, ..." | Standard Plexus logo | Creation date, status |
| Lab Evaluation URL | "Lab Evaluation: {name}" | "Evaluation results for {scorecard} - {score}: {metric1}%, {metric2}%, ..." | Standard Plexus logo | Experience type, duration |
| Dashboard | "Plexus Dashboard" | "Access your AI evaluation dashboard" | Dashboard screenshot | N/A |
| Documentation | "{topic} - Plexus Documentation" | "Learn about {topic} in Plexus" | Documentation icon | Topic category |

## Implementation Plan

### Phase 1: Foundation
1. Create utility functions for metadata generation
   - Create a shared utility file for metadata generation
   - Implement the `formatEvaluationSummary` function for extracting and formatting metrics
   - Add type definitions for evaluation data structures
   - Add tests for the utility function with various metric formats

2. Update root layout with improved default metadata
   - Enhance the default image with better branding
   - Refine default descriptions
   - Ensure all required metadata fields are present

### Phase 2: Evaluation Share URL Implementation (Priority)
1. Implement `generateMetadata` for evaluation share routes
   - Add data fetching in the metadata generation function
   - Use the `formatEvaluationSummary` function to generate the description
   - Set the title based on evaluation name

2. Test evaluation share URL preview rendering
   - Test across multiple platforms (Slack, Discord, Twitter, etc.)
   - Verify text summary displays correctly
   - Ensure data is appropriately truncated for preview limits

### Phase 3: Lab Evaluation URL Implementation
1. Implement `generateMetadata` for lab evaluation routes
   - Add data fetching for lab evaluation metadata
   - Use the same `formatEvaluationSummary` function for consistency
   - Set appropriate titles

2. Test lab evaluation URL preview rendering
   - Test across multiple platforms
   - Verify correct rendering of all metadata elements

### Phase 4: Documentation and Refinement
1. Document the metadata implementation
   - Update this plan with implementation details
   - Create developer documentation for adding metadata to new routes
   - Document the `formatEvaluationSummary` function for reuse

2. Refine based on testing feedback
   - Adjust summary format based on user feedback
   - Optimize for readability across platforms

## Testing Strategy
1. **Manual Testing**: Test URL sharing on each target platform
2. **Automated Testing**: Create tests for the `formatEvaluationSummary` function with various input formats
3. **Validation Tools**: Use Open Graph validators to verify metadata correctness

## Resources
- [Next.js Metadata Documentation](https://nextjs.org/docs/app/building-your-application/optimizing/metadata)
- [Open Graph Protocol](https://ogp.me/)
- [Twitter Card Documentation](https://developer.twitter.com/en/docs/twitter-for-websites/cards/overview/abouts-cards)
- [Schema.org](https://schema.org/)
- [Open Graph Debugger](https://developers.facebook.com/tools/debug/)
- [Twitter Card Validator](https://cards-dev.twitter.com/validator)

## Next Steps
1. Begin implementation of the `formatEvaluationSummary` utility function
2. Create tests for the utility function with various metric formats
3. Implement evaluation share URL metadata generation (priority)
4. Test on target platforms and refine as needed 