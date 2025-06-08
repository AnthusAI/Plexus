# Plexus FeedbackAnalysisEvaluation Enhancement Plan

**Status Legend:**
*   ⬜ Not Started / To Do
*   🟡 In Progress
*   ✅ Completed

## Introduction

This document outlines the plan for enhancing the FeedbackAnalysisEvaluation component within the Plexus platform's reporting system. The enhancements will focus on improving the display of metrics through gauges, optimizing responsive layouts, implementing collapsible/expandable views for detailed information, and adding support for downloading log files and drilling into individual feedback analysis details.

## Core Requirements - Updated

The enhanced FeedbackAnalysisEvaluation component needs to:

1. ✅ Display two key gauges:
   - Agreement (AC1)
   - Accuracy
   - ~~Precision~~ (Removed per requirements update)
   - ~~Recall~~ (Removed per requirements update)

2. ✅ Implement responsive variations to display effectively across different screen widths

3. ✅ In collapsed mode:
   - Show the score name
   - Show Items count and Agreements count
   - Display both gauges (Agreement and Accuracy)
   - Show any warnings if present

4. ✅ In expanded mode:
   - Display class distribution visualization
   - Display predicted class distribution
   - Display confusion matrix
   - Display EvaluationListAccuracyBar for agreement accuracy

5. Provide access to logs:
   - Add UI for downloading log files stored in S3 via Amplify Gen2's storage mechanism
   - Display log file availability and controls

6. Support detailed analysis drilling:
   - Implement mechanism to load and parse JSON attachment files from S3
   - Create UI for exploring individual comparison details stored in these JSON files
   - Handle the asynchronous loading of this data which is not directly available from the API

## Progress Summary

We have successfully implemented multiple phases of the enhancement:

✅ **Flat Design Implementation**:
- Removed all borders, shadows, and depth-creating elements
- Implemented a clean, flat design with a beachy card background
- Ensured consistency with Plexus design language

✅ **Component Structure and Layout**:
- Created a clean layout with collapsible/expandable functionality
- Implemented proper spacing and organization of elements
- Added responsive sizing for different screen widths

✅ **Gauge Implementation**:
- Implemented two gauges (Agreement and Accuracy) in the collapsed view
- Added proper handling for missing data
- Used appropriate styling and size for gauges

✅ **Metadata Display**:
- Added Items and Agreements counts in the collapsed view
- Used positive language ("Agreements" instead of "Mismatches")
- Implemented clean horizontal layout

✅ **Warning System**:
- Added warning display with icon and message
- Ensured warnings are always visible in collapsed mode
- Used appropriate styling for warning alerts

✅ **Expanded View**:
- Implemented visualizations (class distribution, predicted distribution, confusion matrix)
- Added EvaluationListAccuracyBar for agreement accuracy
- Created clean separation between collapsed and expanded views

## Implementation Plan & Checklist (Updated)

### Phase 1: Component Structure and Responsive Layout

*   ✅ **Analyze Current Implementation:**
    *   Reviewed the existing FeedbackAnalysisEvaluation component structure
    *   Identified elements to keep, modify, or add
    *   Determined optimal responsive breakpoints based on dashboard layout

*   ✅ **Redesign Component Structure:**
    *   Created layout for gauge placement
    *   Implemented collapsible/expandable container with smooth transitions
    *   Designed header with score name and collapse/expand toggle

*   ✅ **Update Props Interface:**
    *   Updated `FeedbackAnalysisEvaluationData` to include any additional properties needed
    *   Ensured backward compatibility with existing implementations

### Phase 2: Gauge Implementation

*   ✅ **Implement Gauge Display:**
    *   Added gauge components for agreement and accuracy metrics
    *   Ensured consistent styling and size
    *   Added appropriate labels and value formatting for each gauge

*   ✅ **Create Gauge Layout Components:**
    *   Implemented responsive layout for gauges
    *   Created container components for collapsed and expanded views
    *   Added transitions for smooth state changes

*   ✅ **Handle Missing Data:**
    *   Implemented fallbacks for when certain metrics are missing (null/undefined)
    *   Added visual indicators for unavailable data
    *   Ensured component doesn't break with partial data

### Phase 3: Expanded View Implementation

*   ✅ **Implement Class Distribution Display:**
    *   Added visualization for actual class distribution
    *   Implemented responsive sizing based on available space

*   ✅ **Implement Predicted Class Distribution:**
    *   Added visualization for predicted class distribution
    *   Ensured consistency with actual class distribution visualization

*   ✅ **Implement Confusion Matrix:**
    *   Added confusion matrix visualization
    *   Ensured readability on various screen sizes

*   ✅ **Add Agreement Accuracy Bar:**
    *   Implemented EvaluationListAccuracyBar for visualizing agreement accuracy
    *   Ensured proper calculation of agreement percentage
    *   Placed below other visualizations as requested

### Phase 4: Log File Access Implementation (Remaining)

*   ⬜ **Research Amplify Gen2 S3 Integration:**
    *   Review Amplify Gen2 documentation for S3 storage access
    *   Identify required authentication and permission requirements
    *   Understand file path structure and naming conventions

*   ⬜ **Implement Log File Access UI:**
    *   Add download button/link for log files
    *   Create loading state indicators
    *   Implement error handling for failed downloads
    *   Add explanatory text about log content

*   ⬜ **Implement S3 Download Functionality:**
    *   Create utility function for S3 file access using Amplify APIs
    *   Handle authentication and permissions
    *   Implement file download mechanism (browser download)
    *   Add logging for download operations

### Phase 5: Detailed Analysis Drilling Implementation (Remaining)

*   ⬜ **Design Data Loading Mechanism:**
    *   Create utility functions for loading JSON files from S3
    *   Implement caching to prevent redundant downloads
    *   Handle large JSON files efficiently

*   ⬜ **Create JSON Parser and Data Structure:**
    *   Develop parser for the specific JSON format
    *   Create data structure for individual comparison details
    *   Implement filtering and sorting capabilities

*   ⬜ **Implement Detailed View UI:**
    *   Design UI for displaying individual comparisons
    *   Create pagination or virtualized list for large datasets
    *   Implement filtering controls
    *   Add sorting options
    *   Create detail view for individual comparison items

*   ⬜ **Integrate with Main Component:**
    *   Add "View Details" button/link in expanded mode
    *   Implement modal or panel for detailed view
    *   Connect data loading with UI display
    *   Handle loading states and errors

### Phase 6: Refinements and Testing

*   ✅ **Warning Display Implementation:**
    *   Created warning banner/indicator for collapsed mode
    *   Implemented logic to determine when warnings should appear
    *   Ensured warnings are clearly visible

*   ⬜ **Responsive Testing and Refinement:**
    *   Test component at various screen widths
    *   Refine breakpoints and layouts as needed
    *   Ensure smooth transitions between different responsive states

*   ⬜ **Accessibility Enhancements:**
    *   Add appropriate ARIA attributes
    *   Ensure keyboard navigation works correctly
    *   Check color contrast for all text and visual elements

### Phase 7: Testing and Documentation

*   ⬜ **Update Storybook Stories:**
    *   Modify existing stories to showcase new features
    *   Add stories for different screen sizes
    *   Create stories for different data scenarios (missing data, warnings, etc.)
    *   Add mock S3 data for log and detail view testing

*   ⬜ **Component Documentation:**
    *   Update component JSDoc comments
    *   Document props and their purposes
    *   Add usage examples in component comments
    *   Document S3 integration patterns

*   ⬜ **Final Testing:**
    *   Test in the actual dashboard environment
    *   Verify integration with FeedbackAnalysis parent component
    *   Ensure smooth rendering in reports
    *   Test S3 file access with various file sizes and network conditions

## Current Status and Next Steps

**Current Status:**
- ✅ Basic component structure, styling, and layout are complete
- ✅ Gauges, metadata, and warning system are implemented
- ✅ Expanded view with visualizations and accuracy bar is complete
- 🟡 Overall progress: ~60% complete

**Next Steps for Next Session:**
1. Implement log file access functionality
2. Add detailed analysis drilling capability
3. Complete responsive testing and refinements
4. Add accessibility enhancements
5. Update Storybook stories and documentation
6. Perform final testing in the dashboard environment 