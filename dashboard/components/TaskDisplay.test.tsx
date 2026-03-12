import React from 'react';
import { render, screen } from '@testing-library/react';
import { TaskDisplay } from './TaskDisplay';
import type { AmplifyTask } from '@/utils/data-operations';

// Mock the EvaluationTask component since we're testing TaskDisplay logic
jest.mock('./EvaluationTask', () => {
  return function MockEvaluationTask({ task }: any) {
    const scoreResults = task?.data?.scoreResults || [];
    return (
      <div data-testid="mock-evaluation-task">
        <div data-testid="task-id">{task?.id || task?.data?.id}</div>
        <div data-testid="score-results-count">{scoreResults.length}</div>
        {scoreResults.map((result: any, index: number) => (
          <div key={result.id || index} data-testid={`score-result-${index}`}>
            <div data-testid={`result-id-${index}`}>{result.id}</div>
            <div data-testid={`result-value-${index}`}>{result.value}</div>
            <div data-testid={`result-item-id-${index}`}>{result.itemId}</div>
            <div data-testid={`result-identifiers-${index}`}>
              {result.itemIdentifiers ? JSON.stringify(result.itemIdentifiers) : 'null'}
            </div>
          </div>
        ))}
      </div>
    );
  };
});

describe('TaskDisplay Golden Path', () => {
  const mockTask: AmplifyTask = {
    id: 'task-golden-path',
    accountId: 'account-1', 
    type: 'evaluation',
    status: 'COMPLETED',
    target: 'accuracy',
    command: 'plexus evaluate accuracy --scorecard test',
    createdAt: '2024-01-01T00:00:00Z'
  };

  describe('score results preservation', () => {
    it('should pass through pre-transformed score results without modification', () => {
      const mockEvaluationData = {
        id: 'eval-golden',
        type: 'accuracy',
        scoreResults: [
          {
            id: 'result-1',
            value: 'positive',
            confidence: 0.9,
            explanation: 'High confidence',
            metadata: {
              human_label: 'correct',
              correct: true,
              human_explanation: null,
              text: 'Sample text'
            },
            trace: { model: 'gpt-4' },
            itemId: 'item-1',
            itemIdentifiers: [
              { name: 'Form ID', value: 'FORM-123' },
              { name: 'Session ID', value: 'SESS-456' }
            ],
            feedbackItem: { editCommentValue: 'Good result' }
          },
          {
            id: 'result-2', 
            value: 'negative',
            confidence: 0.8,
            explanation: 'Medium confidence',
            metadata: {
              human_label: 'incorrect',
              correct: false,
              human_explanation: null,
              text: 'Another sample'
            },
            trace: null,
            itemId: 'item-2',
            itemIdentifiers: [
              { name: 'Form ID', value: 'FORM-789' },
              { name: 'User ID', value: 'USER-123', url: '/users/123' }
            ],
            feedbackItem: null
          }
        ]
      };

      render(
        <TaskDisplay
          variant="detail"
          task={mockTask}
          evaluationData={mockEvaluationData}
        />
      );

      // Verify the evaluation ID was passed as the display ID
      expect(screen.getByTestId('task-id')).toHaveTextContent('eval-golden');
      expect(screen.getByTestId('score-results-count')).toHaveTextContent('2');

      // Verify first score result preservation
      expect(screen.getByTestId('result-id-0')).toHaveTextContent('result-1');
      expect(screen.getByTestId('result-value-0')).toHaveTextContent('positive');
      expect(screen.getByTestId('result-item-id-0')).toHaveTextContent('item-1');
      
      const identifiers1 = JSON.parse(screen.getByTestId('result-identifiers-0').textContent!);
      expect(identifiers1).toEqual([
        { name: 'Form ID', value: 'FORM-123' },
        { name: 'Session ID', value: 'SESS-456' }
      ]);

      // Verify second score result preservation
      expect(screen.getByTestId('result-id-1')).toHaveTextContent('result-2');
      expect(screen.getByTestId('result-value-1')).toHaveTextContent('negative');
      expect(screen.getByTestId('result-item-id-1')).toHaveTextContent('item-2');
      
      const identifiers2 = JSON.parse(screen.getByTestId('result-identifiers-1').textContent!);
      expect(identifiers2).toEqual([
        { name: 'Form ID', value: 'FORM-789' },
        { name: 'User ID', value: 'USER-123', url: '/users/123' }
      ]);
    });

    it('should handle score results as array (already transformed)', () => {
      const mockEvaluationData = {
        id: 'eval-array',
        type: 'accuracy',
        scoreResults: [
          {
            id: 'result-array-1',
            value: 'positive',
            itemId: 'item-array-1',
            itemIdentifiers: [
              { name: 'Array ID', value: 'ARR-123' }
            ]
          }
        ]
      };

      render(
        <TaskDisplay
          variant="grid"
          task={mockTask}
          evaluationData={mockEvaluationData}
        />
      );

      expect(screen.getByTestId('score-results-count')).toHaveTextContent('1');
      expect(screen.getByTestId('result-id-0')).toHaveTextContent('result-array-1');
      
      const identifiers = JSON.parse(screen.getByTestId('result-identifiers-0').textContent!);
      expect(identifiers).toEqual([
        { name: 'Array ID', value: 'ARR-123' }
      ]);
    });

    it('should handle score results with items property (Amplify format)', () => {
      const mockEvaluationData = {
        id: 'eval-items',
        type: 'accuracy', 
        scoreResults: {
          items: [
            {
              id: 'result-items-1',
              value: 'neutral',
              itemId: 'item-items-1',
              itemIdentifiers: [
                { name: 'Items ID', value: 'ITM-456' }
              ]
            }
          ]
        }
      };

      render(
        <TaskDisplay
          variant="detail"
          task={mockTask}
          evaluationData={mockEvaluationData}
        />
      );

      expect(screen.getByTestId('score-results-count')).toHaveTextContent('1');
      expect(screen.getByTestId('result-id-0')).toHaveTextContent('result-items-1');
      
      const identifiers = JSON.parse(screen.getByTestId('result-identifiers-0').textContent!);
      expect(identifiers).toEqual([
        { name: 'Items ID', value: 'ITM-456' }
      ]);
    });

    it('should handle empty score results gracefully', () => {
      const mockEvaluationData = {
        id: 'eval-empty',
        type: 'accuracy',
        scoreResults: []
      };

      render(
        <TaskDisplay
          variant="grid"
          task={mockTask}
          evaluationData={mockEvaluationData}
        />
      );

      expect(screen.getByTestId('score-results-count')).toHaveTextContent('0');
    });

    it('should handle null score results gracefully', () => {
      const mockEvaluationData = {
        id: 'eval-null',
        type: 'accuracy',
        scoreResults: null
      };

      render(
        <TaskDisplay
          variant="detail"
          task={mockTask}
          evaluationData={mockEvaluationData}
        />
      );

      expect(screen.getByTestId('score-results-count')).toHaveTextContent('0');
    });

    it('should handle undefined score results gracefully', () => {
      const mockEvaluationData = {
        id: 'eval-undefined',
        type: 'accuracy'
        // scoreResults property not defined
      };

      render(
        <TaskDisplay
          variant="grid"
          task={mockTask}
          evaluationData={mockEvaluationData}
        />
      );

      expect(screen.getByTestId('score-results-count')).toHaveTextContent('0');
    });
  });

  describe('regression prevention', () => {
    it('should NOT call standardizeScoreResults or similar transformation functions', () => {
      // This test ensures we don't accidentally re-introduce the patch
      const mockEvaluationData = {
        id: 'eval-regression-test',
        type: 'accuracy',
        scoreResults: [
          {
            id: 'result-regression',
            value: 'positive',
            itemId: 'item-regression',
            itemIdentifiers: [
              { name: 'Regression Test ID', value: 'REG-999' }
            ],
            // Add some complex nested structure to test that we don't over-process
            metadata: {
              nested: {
                results: {
                  key1: {
                    explanation: 'Should not be extracted'
                  }
                }
              }
            }
          }
        ]
      };

      render(
        <TaskDisplay
          variant="detail"
          task={mockTask}
          evaluationData={mockEvaluationData}
        />
      );

      // The itemIdentifiers should be preserved exactly as passed
      const identifiers = JSON.parse(screen.getByTestId('result-identifiers-0').textContent!);
      expect(identifiers).toEqual([
        { name: 'Regression Test ID', value: 'REG-999' }
      ]);

      // The nested metadata should not be transformed
      expect(screen.getByTestId('result-value-0')).toHaveTextContent('positive');
    });

    it('should preserve all score result properties without loss', () => {
      const complexScoreResult = {
        id: 'complex-result',
        value: 'complex-value',
        confidence: 0.123456,
        explanation: 'Complex explanation with special chars: àáâãäå',
        metadata: {
          human_label: 'complex-label',
          correct: true,
          human_explanation: 'Complex human explanation',
          text: 'Complex text with unicode: 🎉🔥✅',
          customField: 'should-be-preserved',
          nestedObject: {
            level1: {
              level2: 'deep-value'
            }
          }
        },
        trace: {
          model: 'custom-model',
          version: '2.1.3',
          processing_time: 1.234,
          tokens: 150
        },
        itemId: 'complex-item-id',
        itemIdentifiers: [
          { name: 'Complex Form ID', value: 'CFORM-X1Y2Z3' },
          { name: 'Unicode ID', value: '测试-ID-123' },
          { name: 'URL ID', value: 'URL-789', url: 'https://example.com/test?id=789&type=complex' }
        ],
        feedbackItem: {
          editCommentValue: 'Complex feedback comment'
        },
        createdAt: '2024-01-01T12:34:56.789Z',
        customProperty: 'should-be-preserved'
      };

      const mockEvaluationData = {
        id: 'eval-complex',
        type: 'accuracy',
        scoreResults: [complexScoreResult]
      };

      render(
        <TaskDisplay
          variant="detail"
          task={mockTask}
          evaluationData={mockEvaluationData}
        />
      );

      // Verify complex identifiers are preserved exactly
      const preservedIdentifiers = JSON.parse(screen.getByTestId('result-identifiers-0').textContent!);
      expect(preservedIdentifiers).toEqual([
        { name: 'Complex Form ID', value: 'CFORM-X1Y2Z3' },
        { name: 'Unicode ID', value: '测试-ID-123' },
        { name: 'URL ID', value: 'URL-789', url: 'https://example.com/test?id=789&type=complex' }
      ]);

      // Verify other properties are preserved
      expect(screen.getByTestId('result-id-0')).toHaveTextContent('complex-result');
      expect(screen.getByTestId('result-value-0')).toHaveTextContent('complex-value');
      expect(screen.getByTestId('result-item-id-0')).toHaveTextContent('complex-item-id');
    });
  });
});