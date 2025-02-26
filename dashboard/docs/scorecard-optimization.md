# Scorecard Data Fetching Optimization

## Problem

The original implementation of the scorecard dashboard had performance issues due to:

1. Multiple separate GraphQL queries for fetching scorecards, sections, and scores
2. Nested loops that executed many queries in sequence
3. Inefficient data structure that required additional processing

This resulted in slow loading times, especially for scorecards with many sections and scores.

## Solution

We implemented a comprehensive optimization strategy:

1. **Single GraphQL Query**: Created custom GraphQL queries that fetch all necessary data (scorecard, sections, scores) in a single request.

2. **Utility Functions**: Implemented utility functions in `dashboard/utils/scorecard-operations.ts` to:
   - Fetch a single scorecard with all its sections and scores
   - List all scorecards with their sections and scores
   - List scorecards by account ID with their sections and scores

3. **Component Updates**: Updated the following components to work with the optimized data structure:
   - `ScorecardsComponent` in `dashboard/components/scorecards-dashboard.tsx`
   - `ScorecardForm` in `dashboard/components/scorecards/create-edit-form/index.tsx`
   - `ScoreCount` in `dashboard/components/scorecards/score-count.tsx`

## Implementation Details

### GraphQL Queries

Created `dashboard/graphql/scorecard-queries.ts` with the following queries:

- `GET_SCORECARD_WITH_SECTIONS_AND_SCORES`: Fetches a single scorecard with all its sections and scores
- `LIST_SCORECARDS_WITH_SECTIONS_AND_SCORES`: Lists all scorecards with their sections and scores
- `LIST_SCORECARDS_BY_ACCOUNT_ID`: Lists scorecards by account ID with their sections and scores

### Utility Functions

Implemented `dashboard/utils/scorecard-operations.ts` with the following functions:

- `getScorecardWithSectionsAndScores`: Fetches a single scorecard with all its sections and scores
- `listScorecardsWithSectionsAndScores`: Lists all scorecards with their sections and scores
- `listScorecardsByAccountId`: Lists scorecards by account ID with their sections and scores
- `convertToAmplifyScorecard`: Converts GraphQL response to Amplify model format

### Component Updates

1. **ScorecardsComponent**:
   - Replaced multiple separate queries with a single call to `listScorecardsByAccountId`
   - Eliminated nested loops for fetching sections and scores
   - Simplified the `handleEdit` function to use `getScorecardWithSectionsAndScores`

2. **ScorecardForm**:
   - Updated to work with the pre-loaded data structure
   - Simplified the data processing logic

3. **ScoreCount**:
   - Removed nested loops for fetching scores
   - Simplified the score counting logic

## Benefits

1. **Reduced Network Requests**: From many separate queries to a single comprehensive query
2. **Eliminated Nested Loops**: Removed performance bottlenecks caused by sequential queries
3. **Improved Data Structure**: More efficient and easier to work with
4. **Faster Loading Times**: Especially noticeable for scorecards with many sections and scores

## Future Improvements

1. **Pagination**: Implement pagination for large datasets
2. **Caching**: Add caching mechanisms to further improve performance
3. **Optimistic Updates**: Implement optimistic updates for better user experience during edits 