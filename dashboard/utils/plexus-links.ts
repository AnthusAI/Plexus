export type PlexusRecordType = 'scorecard' | 'score' | 'item' | 'evaluation' | 'report';

interface PlexusUrlOptions {
  recordType: PlexusRecordType;
  id: string;
  parentId?: string; // For nested resources like scores within scorecards
}

export function getDashboardUrl(options: PlexusUrlOptions): string {
  const { recordType, id, parentId } = options;

  switch (recordType) {
    case 'scorecard':
      return `/lab/scorecards/${id}`;
    case 'score':
      if (parentId) {
        return `/lab/scorecards/${parentId}/scores/${id}`;
      }
      // Fallback or alternative link if parentId is not available,
      // though for scores, parentId (scorecardId) is usually essential.
      // Consider linking to a generic score search or a specific score page if applicable.
      // For now, let's assume a score always has a scorecard context for its primary dashboard link.
      console.warn(`Score URL generation without parentId for score ${id} might be incomplete.`);
      return `/lab/scorecards?scoreId=${id}`; // Example fallback
    case 'item':
      return `/lab/items/${id}`;
    case 'evaluation':
      return `/lab/evaluations/${id}`;
    case 'report':
      return `/lab/reports/${id}`;
    default:
      // eslint-disable-next-line no-case-declarations
      const exhaustiveCheck: never = recordType;
      console.warn(`Unknown record type: ${exhaustiveCheck}`);
      return '/'; // Fallback to a default or error page
  }
}

// Example Usage:
// getDashboardUrl({ recordType: 'scorecard', id: 'sc-123' }); // -> '/lab/scorecards/sc-123'
// getDashboardUrl({ recordType: 'score', id: 's-456', parentId: 'sc-123' }); // -> '/lab/scorecards/sc-123/scores/s-456'
// getDashboardUrl({ recordType: 'item', id: 'item-789' }); // -> '/lab/items/item-789' 