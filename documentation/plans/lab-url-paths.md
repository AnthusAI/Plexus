# Lab URL Paths and Deep Linking Implementation

## Overview

This document explains how we implemented deep linking in the Plexus dashboard, specifically for the evaluations page. The implementation allows users to:

1. Select an evaluation from the list
2. Have the URL update to reflect the selected evaluation (e.g., `/lab/evaluations/[id]`)
3. Navigate directly to a specific evaluation via URL
4. Use browser back/forward navigation
5. All without causing full page re-renders

## Problem

The initial implementation used Next.js router navigation (`router.replace()`) to update the URL when an evaluation was selected. This caused a full page re-render, which:

- Disrupted the user experience with a visible flash
- Reset UI state unnecessarily
- Caused performance issues

## Solution: Client-Side URL Updates with History API

We implemented a solution using the browser's native History API to update the URL without triggering a full page navigation/re-render. This approach is sometimes called "shallow routing" in Next.js terminology.

### Key Components

1. **URL Updates via History API**: Using `window.history.pushState()` to update the URL without navigation
2. **Popstate Event Listener**: Handling browser back/forward navigation
3. **Initial Deep Link Handling**: Supporting direct navigation to evaluation URLs

### Implementation Details

#### 1. Click Handler for Evaluation Selection

When a user clicks on an evaluation in the list:

```typescript
const getEvaluationClickHandler = useCallback((evaluationId: string) => {
  return (e?: React.MouseEvent | React.SyntheticEvent | any) => {
    // Prevent default if it's an event object
    if (e && typeof e.preventDefault === 'function') {
      e.preventDefault();
    }
    
    if (evaluationId !== selectedEvaluationId) {
      // Update state first
      setSelectedEvaluationId(evaluationId);
      
      // Then update URL without triggering a navigation/re-render
      const newPathname = `/lab/evaluations/${evaluationId}`;
      window.history.pushState(null, '', newPathname);
      
      if (isNarrowViewport) {
        setIsFullWidth(true);
      }
    }
  };
}, [selectedEvaluationId, isNarrowViewport]);
```

This handler:
- Updates the component state with the selected evaluation ID
- Updates the URL using `window.history.pushState()` without causing navigation
- Adjusts the UI layout if needed

#### 2. Handling Browser Back/Forward Navigation

To ensure the browser's back and forward buttons work correctly:

```typescript
useEffect(() => {
  const handlePopState = (event: PopStateEvent) => {
    // Extract evaluation ID from URL if present
    const match = window.location.pathname.match(/\/lab\/evaluations\/([^\/]+)$/);
    const idFromUrl = match ? match[1] : null;
    
    // Update the selected evaluation ID based on the URL
    setSelectedEvaluationId(idFromUrl);
  };

  // Add event listener for popstate (browser back/forward)
  window.addEventListener('popstate', handlePopState);
  
  // Clean up event listener on unmount
  return () => {
    window.removeEventListener('popstate', handlePopState);
  };
}, []);
```

This effect:
- Listens for the browser's `popstate` event (triggered by back/forward navigation)
- Extracts the evaluation ID from the URL
- Updates the component state to match the URL

#### 3. Initial Deep Link Handling

To support direct navigation to a specific evaluation URL:

```typescript
useEffect(() => {
  // If we have an ID in the URL and we're on the main evaluations page
  if (params && 'id' in params && pathname === `/evaluations/${params.id}`) {
    setSelectedEvaluationId(params.id as string);
  }
}, [params, pathname]);
```

This effect:
- Checks if there's an evaluation ID in the URL parameters
- Sets the selected evaluation ID accordingly

#### 4. Consistent URL Handling in Other Actions

The same approach is used in other actions like closing an evaluation:

```typescript
const handleCloseEvaluation = () => {
  setSelectedEvaluationId(null);
  setIsFullWidth(false);
  
  // Update URL without triggering a navigation/re-render
  window.history.pushState(null, '', '/lab/evaluations');
};
```

## Benefits

This implementation provides several benefits:

1. **Improved Performance**: No unnecessary page re-renders
2. **Better UX**: No visual flashing or state resets when selecting items
3. **Preserved State**: UI state is maintained during navigation
4. **SEO and Sharing**: URLs still reflect the current view for sharing and bookmarking
5. **Browser Navigation**: Back/forward buttons work as expected

## Considerations

1. **Server-Side Rendering**: This approach focuses on client-side behavior; server-side routes must still be configured correctly
2. **Browser Support**: Uses standard History API supported by all modern browsers
3. **Analytics**: URL changes via History API may need special handling for analytics tools

## Alternative Approaches

1. **Next.js App Router**: In newer Next.js versions, the App Router provides more built-in support for this pattern
2. **URL State Libraries**: Libraries like `use-query-params` can help manage URL state
3. **State Management**: For complex apps, consider using a state management library that integrates with the URL

## Conclusion

By using the browser's History API instead of router navigation, we've created a smoother user experience that maintains the benefits of deep linking without the performance cost of full page re-renders. 