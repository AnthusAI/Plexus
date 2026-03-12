"use client";

import React, { useState } from 'react';
import { useFeedbackItemsByAnswers } from '@/hooks/use-feedback-items-by-answers';
import { useAccount } from '@/app/contexts/AccountContext';
import { Button } from '@/components/ui/button';

/**
 * Test component to verify the GSI functionality for feedback items
 * This component can be temporarily added to a page to test the GSI queries
 */
export const TestFeedbackGSI: React.FC = () => {
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { fetchFeedbackItems } = useFeedbackItemsByAnswers();
  const { selectedAccount } = useAccount();

  const testGSIQuery = async () => {
    if (!selectedAccount) {
      setError('No account selected');
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      // Test with multiple scenarios to check different combinations
      console.log('=== Testing GSI Functionality ===');
      
      const testCases = [
        {
          name: 'Test Case 1: Yes->No',
          filter: {
            accountId: selectedAccount.id,
            scorecardId: 'f3e2c4b2-27ed-48d5-b24a-e7ae74b5c5d4', // CMG scorecard ID (replace with actual)
            scoreId: 'a7bb8592-8c4a-4c8c-8eb6-1b8c7c7a6f9d', // Score ID (replace with actual)
            predicted: 'Yes',
            actual: 'No'
          }
        },
        {
          name: 'Test Case 2: No->Yes', 
          filter: {
            accountId: selectedAccount.id,
            scorecardId: 'f3e2c4b2-27ed-48d5-b24a-e7ae74b5c5d4',
            scoreId: 'a7bb8592-8c4a-4c8c-8eb6-1b8c7c7a6f9d',
            predicted: 'No',
            actual: 'Yes'
          }
        }
      ];
      
      const allResults: any[] = [];
      
      for (const testCase of testCases) {
        console.log(`Testing: ${testCase.name}`, testCase.filter);
        
        try {
          const caseResults = await fetchFeedbackItems(testCase.filter);
          console.log(`${testCase.name} results:`, caseResults.length, 'items');
          allResults.push({
            testCase: testCase.name,
            filter: testCase.filter,
            results: caseResults,
            count: caseResults.length
          });
        } catch (caseErr) {
          console.error(`${testCase.name} failed:`, caseErr);
          allResults.push({
            testCase: testCase.name,
            filter: testCase.filter,
            error: caseErr instanceof Error ? caseErr.message : 'Unknown error',
            count: 0
          });
        }
      }
      
      setResults(allResults);
      console.log('=== All GSI Test Results ===', allResults);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      console.error('GSI Test Error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 border rounded-lg bg-muted/50 max-w-2xl">
      <h3 className="text-lg font-semibold mb-4">Test Feedback Items GSI</h3>
      
      <div className="mb-4">
        <p className="text-sm text-muted-foreground mb-2">
          Selected Account: {selectedAccount?.name || 'None'}
        </p>
        
        <Button 
          onClick={testGSIQuery} 
          disabled={loading || !selectedAccount}
          className="mb-4"
        >
          {loading ? 'Testing...' : 'Test GSI Query'}
        </Button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-100 text-red-800 rounded">
          <strong>Error:</strong> {error}
        </div>
      )}

      {results.length > 0 && (
        <div className="mb-4">
          <h4 className="font-medium mb-2">Test Results:</h4>
          {results.map((result: any, index: number) => (
            <div key={index} className="mb-3 p-3 bg-white rounded border">
              <div className="flex justify-between items-center mb-2">
                <h5 className="font-medium text-sm">{result.testCase}</h5>
                <span className={`px-2 py-1 rounded text-xs ${
                  result.error ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                }`}>
                  {result.error ? 'Failed' : `${result.count} items`}
                </span>
              </div>
              
              {result.error && (
                <div className="text-red-600 text-xs mb-2">
                  Error: {result.error}
                </div>
              )}
              
              <details className="text-xs">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                  Show details
                </summary>
                <pre className="mt-2 p-2 bg-gray-50 rounded overflow-auto max-h-40">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </details>
            </div>
          ))}
        </div>
      )}

      <div className="text-xs text-muted-foreground">
        <p>This component tests the new GSI functionality for fetching feedback items.</p>
        <p>Check the browser console for detailed logs about the GSI query execution.</p>
      </div>
    </div>
  );
};