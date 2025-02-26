// Simple performance test script for scorecard operations

// Import required modules
const { execSync } = require('child_process');

console.log('=== SCORECARD PERFORMANCE TEST ===');
console.log('This script will test the performance of the old vs. new approach for fetching scorecard data.');
console.log('');

// Function to run a command and measure its execution time
function runCommand(command, description) {
  console.log(`Running: ${description}`);
  console.time(description);
  
  try {
    const output = execSync(command, { encoding: 'utf8' });
    console.log(output);
  } catch (error) {
    console.error(`Error executing command: ${error.message}`);
    if (error.stdout) console.log(error.stdout);
    if (error.stderr) console.error(error.stderr);
  }
  
  console.timeEnd(description);
  console.log('');
}

// Test the old approach (multiple queries)
const oldApproachCommand = `
node -e "
const { amplifyClient } = require('./utils/amplify-client');

async function fetchScorecardsOldWay() {
  console.time('Old Approach');
  
  // Get account ID first
  const accountResult = await amplifyClient.Account.list({
    filter: { key: { eq: 'call-criteria' } }
  });

  if (accountResult.data.length === 0) {
    console.log('No account found');
    return;
  }

  const accountId = accountResult.data[0].id;
  
  // Fetch scorecards
  const scorecardsResult = await amplifyClient.Scorecard.list({
    filter: { accountId: { eq: accountId } }
  });
  
  const scorecards = scorecardsResult.data;
  console.log(\`Found \${scorecards.length} scorecards\`);
  
  // For each scorecard, fetch sections
  for (const scorecard of scorecards) {
    const sectionsResult = await scorecard.sections();
    const sections = sectionsResult.data;
    console.log(\`Scorecard \${scorecard.name}: Found \${sections.length} sections\`);
    
    // For each section, fetch scores
    for (const section of sections) {
      const scoresResult = await section.scores();
      const scores = scoresResult.data;
      console.log(\`Section \${section.name}: Found \${scores.length} scores\`);
    }
  }
  
  console.timeEnd('Old Approach');
}

fetchScorecardsOldWay().catch(console.error);
"`;

// Test the new approach (single query)
const newApproachCommand = `
node -e "
const { amplifyClient } = require('./utils/amplify-client');
const { listScorecardsByAccountId } = require('./utils/scorecard-operations');

async function fetchScorecardsNewWay() {
  console.time('New Approach');
  
  // Get account ID first
  const accountResult = await amplifyClient.Account.list({
    filter: { key: { eq: 'call-criteria' } }
  });

  if (accountResult.data.length === 0) {
    console.log('No account found');
    return;
  }

  const accountId = accountResult.data[0].id;
  
  // Use the new utility function to fetch all scorecards with sections and scores in one go
  const result = await listScorecardsByAccountId(accountId);
  const scorecards = result.data;
  
  console.log(\`Found \${scorecards.length} scorecards\`);
  
  // Log some stats to verify data is complete
  for (const scorecard of scorecards) {
    const sectionsResult = await scorecard.sections();
    const sections = sectionsResult.data;
    console.log(\`Scorecard \${scorecard.name}: Found \${sections.length} sections\`);
    
    for (const section of sections) {
      const scoresResult = await section.scores();
      const scores = scoresResult.data;
      console.log(\`Section \${section.name}: Found \${scores.length} scores\`);
    }
  }
  
  console.timeEnd('New Approach');
}

fetchScorecardsNewWay().catch(console.error);
"`;

// Run the tests
runCommand(oldApproachCommand, 'Old Approach (Multiple Queries)');
runCommand(newApproachCommand, 'New Approach (Single Query)');

console.log('=== PERFORMANCE TEST COMPLETED ==='); 