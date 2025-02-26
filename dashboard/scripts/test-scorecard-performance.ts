import { amplifyClient } from "@/utils/amplify-client";
import { listScorecardsByAccountId, getScorecardWithSectionsAndScores } from "@/utils/scorecard-operations";

const ACCOUNT_KEY = 'call-criteria';

// Old approach: Multiple separate queries with nested loops
async function fetchScorecardsOldWay() {
  console.time('Old Approach');
  
  // Get account ID first
  const accountResult = await amplifyClient.Account.list({
    filter: { key: { eq: ACCOUNT_KEY } }
  });

  if (accountResult.data.length === 0) {
    console.log('No account found with key:', ACCOUNT_KEY);
    return;
  }

  const accountId = accountResult.data[0].id;
  
  // Fetch scorecards
  const scorecardsResult = await amplifyClient.Scorecard.list({
    filter: { accountId: { eq: accountId } }
  });
  
  const scorecards = scorecardsResult.data;
  console.log(`Found ${scorecards.length} scorecards`);
  
  // For each scorecard, fetch sections
  for (const scorecard of scorecards) {
    const sectionsResult = await amplifyClient.ScorecardSection.list({
      filter: { scorecardId: { eq: scorecard.id } }
    });
    
    const sections = sectionsResult.data;
    console.log(`Scorecard ${scorecard.name}: Found ${sections.length} sections`);
    
    // For each section, fetch scores
    for (const section of sections) {
      const scoresResult = await amplifyClient.Score.list({
        filter: { sectionId: { eq: section.id } }
      });
      
      const scores = scoresResult.data;
      console.log(`Section ${section.name}: Found ${scores.length} scores`);
    }
  }
  
  console.timeEnd('Old Approach');
}

// New approach: Single comprehensive query
async function fetchScorecardsNewWay() {
  console.time('New Approach');
  
  // Get account ID first
  const accountResult = await amplifyClient.Account.list({
    filter: { key: { eq: ACCOUNT_KEY } }
  });

  if (accountResult.data.length === 0) {
    console.log('No account found with key:', ACCOUNT_KEY);
    return;
  }

  const accountId = accountResult.data[0].id;
  
  // Use the new utility function to fetch all scorecards with sections and scores in one go
  const result = await listScorecardsByAccountId(accountId);
  const scorecards = result.data;
  
  console.log(`Found ${scorecards.length} scorecards`);
  
  // Log some stats to verify data is complete
  for (const scorecard of scorecards) {
    const sectionsResult = await scorecard.sections();
    const sections = sectionsResult.data;
    console.log(`Scorecard ${scorecard.name}: Found ${sections.length} sections`);
    
    for (const section of sections) {
      const scoresResult = await section.scores();
      const scores = scoresResult.data;
      console.log(`Section ${section.name}: Found ${scores.length} scores`);
    }
  }
  
  console.timeEnd('New Approach');
}

// Test fetching a single scorecard
async function testSingleScorecardFetch() {
  console.time('Single Scorecard Fetch');
  
  // Get account ID first
  const accountResult = await amplifyClient.Account.list({
    filter: { key: { eq: ACCOUNT_KEY } }
  });

  if (accountResult.data.length === 0) {
    console.log('No account found with key:', ACCOUNT_KEY);
    return;
  }
  
  // Get the first scorecard
  const scorecardsResult = await amplifyClient.Scorecard.list({
    filter: { accountId: { eq: accountResult.data[0].id } },
    limit: 1
  });
  
  if (scorecardsResult.data.length === 0) {
    console.log('No scorecards found');
    return;
  }
  
  const scorecardId = scorecardsResult.data[0].id;
  
  // Use the new utility function to fetch the scorecard with all its data
  const scorecard = await getScorecardWithSectionsAndScores(scorecardId);
  
  if (!scorecard) {
    console.log('Failed to fetch scorecard');
    return;
  }
  
  console.log(`Fetched scorecard: ${scorecard.name}`);
  
  const sectionsResult = await scorecard.sections();
  console.log(`Found ${sectionsResult.data.length} sections`);
  
  console.timeEnd('Single Scorecard Fetch');
}

// Run the tests
async function runTests() {
  console.log('=== PERFORMANCE TEST: OLD VS NEW APPROACH ===');
  
  console.log('\n--- Testing Old Approach ---');
  await fetchScorecardsOldWay();
  
  console.log('\n--- Testing New Approach ---');
  await fetchScorecardsNewWay();
  
  console.log('\n--- Testing Single Scorecard Fetch ---');
  await testSingleScorecardFetch();
}

// Execute the tests
runTests().catch(error => {
  console.error('Error running tests:', error);
}); 