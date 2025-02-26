import { NextResponse } from 'next/server';
import { amplifyClient } from '@/utils/amplify-client';
import { listScorecardsByAccountId, getScorecardWithSectionsAndScores } from '@/utils/scorecard-operations';

const ACCOUNT_KEY = 'call-criteria';

// Define types for our stats
interface SectionStat {
  scorecardName: string;
  sectionCount: number;
}

interface ScoreStat {
  sectionName: string;
  scoreCount: number;
}

interface Stats {
  totalScorecards: number;
  sections: SectionStat[];
  scores: ScoreStat[];
  error?: string;
}

// Helper function to measure execution time
async function measureExecutionTime(fn: () => Promise<any>): Promise<{ result: any; executionTime: number }> {
  const start = performance.now();
  const result = await fn();
  const end = performance.now();
  return { result, executionTime: end - start };
}

// Old approach: Multiple separate queries with nested loops
async function fetchScorecardsOldWay(): Promise<Stats> {
  // Get account ID first
  const accountResult = await amplifyClient.Account.list({
    filter: { key: { eq: ACCOUNT_KEY } }
  });

  if (accountResult.data.length === 0) {
    return { totalScorecards: 0, sections: [], scores: [], error: 'No account found with key: ' + ACCOUNT_KEY };
  }

  const accountId = accountResult.data[0].id;
  
  // Fetch scorecards
  const scorecardsResult = await amplifyClient.Scorecard.list({
    filter: { accountId: { eq: accountId } }
  });
  
  const scorecards = scorecardsResult.data;
  const stats: Stats = { totalScorecards: scorecards.length, sections: [], scores: [] };
  
  // For each scorecard, fetch sections
  for (const scorecard of scorecards) {
    const sectionsResult = await scorecard.sections();
    const sections = sectionsResult.data;
    stats.sections.push({ scorecardName: scorecard.name, sectionCount: sections.length });
    
    // For each section, fetch scores
    for (const section of sections) {
      const scoresResult = await section.scores();
      const scores = scoresResult.data;
      stats.scores.push({ sectionName: section.name, scoreCount: scores.length });
    }
  }
  
  return stats;
}

// New approach: Single comprehensive query
async function fetchScorecardsNewWay(): Promise<Stats> {
  // Get account ID first
  const accountResult = await amplifyClient.Account.list({
    filter: { key: { eq: ACCOUNT_KEY } }
  });

  if (accountResult.data.length === 0) {
    return { totalScorecards: 0, sections: [], scores: [], error: 'No account found with key: ' + ACCOUNT_KEY };
  }

  const accountId = accountResult.data[0].id;
  
  // Use the new utility function to fetch all scorecards with sections and scores in one go
  const result = await listScorecardsByAccountId(accountId);
  const scorecards = result.data;
  
  const stats: Stats = { totalScorecards: scorecards.length, sections: [], scores: [] };
  
  // Log some stats to verify data is complete
  for (const scorecard of scorecards) {
    const sectionsResult = await scorecard.sections();
    const sections = sectionsResult.data;
    stats.sections.push({ scorecardName: scorecard.name, sectionCount: sections.length });
    
    for (const section of sections) {
      const scoresResult = await section.scores();
      const scores = scoresResult.data;
      stats.scores.push({ sectionName: section.name, scoreCount: scores.length });
    }
  }
  
  return stats;
}

// Test fetching a single scorecard
async function testSingleScorecardFetch() {
  // Get account ID first
  const accountResult = await amplifyClient.Account.list({
    filter: { key: { eq: ACCOUNT_KEY } }
  });

  if (accountResult.data.length === 0) {
    return { error: 'No account found with key: ' + ACCOUNT_KEY };
  }
  
  // Get the first scorecard
  const scorecardsResult = await amplifyClient.Scorecard.list({
    filter: { accountId: { eq: accountResult.data[0].id } },
    limit: 1
  });
  
  if (scorecardsResult.data.length === 0) {
    return { error: 'No scorecards found' };
  }
  
  const scorecardId = scorecardsResult.data[0].id;
  
  // Use the new utility function to fetch the scorecard with all its data
  const scorecard = await getScorecardWithSectionsAndScores(scorecardId);
  
  if (!scorecard) {
    return { error: 'Failed to fetch scorecard' };
  }
  
  const sectionsResult = await scorecard.sections();
  
  return {
    scorecardName: scorecard.name,
    sectionCount: sectionsResult.data.length
  };
}

export async function GET() {
  try {
    // Run the performance tests
    const oldApproachResult = await measureExecutionTime(fetchScorecardsOldWay);
    const newApproachResult = await measureExecutionTime(fetchScorecardsNewWay);
    const singleScorecardResult = await measureExecutionTime(testSingleScorecardFetch);
    
    // Return the results
    return NextResponse.json({
      oldApproach: {
        executionTime: oldApproachResult.executionTime,
        result: oldApproachResult.result
      },
      newApproach: {
        executionTime: newApproachResult.executionTime,
        result: newApproachResult.result
      },
      singleScorecard: {
        executionTime: singleScorecardResult.executionTime,
        result: singleScorecardResult.result
      }
    });
  } catch (error) {
    console.error('Error running performance test:', error);
    return NextResponse.json({ error: 'Failed to run performance test' }, { status: 500 });
  }
} 