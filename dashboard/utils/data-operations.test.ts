import { transformEvaluation } from './data-operations';
import type { BaseEvaluation } from './data-operations';

describe('transformEvaluation', () => {
  describe('itemIdentifiers extraction', () => {
    it('should extract itemIdentifiers from score results with item relationships', () => {
      const mockEvaluation: BaseEvaluation = {
        id: 'eval-1',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        accuracy: 0.85,
        scoreResults: {
          items: [{
            id: 'result-1',
            value: 'positive',
            confidence: 0.9,
            metadata: {},
            explanation: null,
            trace: null,
            itemId: 'item-1',
            createdAt: '2024-01-01T00:00:00Z',
            item: {
              id: 'item-1',
              externalId: 'ext-1',
              identifiers: null,
              itemIdentifiers: {
                items: [
                  { name: 'Form ID', value: 'FORM-123', position: 1, url: null },
                  { name: 'Session ID', value: 'SESS-456', position: 2, url: null },
                  { name: 'Report ID', value: 'RPT-789', position: 3, url: '/reports/789' }
                ]
              }
            }
          }]
        }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      expect(result!.scoreResults).toHaveLength(1);
      expect(result!.scoreResults![0].itemIdentifiers).toHaveLength(3);
      
      // Check sorted order (by position)
      expect(result!.scoreResults![0].itemIdentifiers![0]).toEqual({
        name: 'Form ID',
        value: 'FORM-123'
      });
      expect(result!.scoreResults![0].itemIdentifiers![1]).toEqual({
        name: 'Session ID',
        value: 'SESS-456'
      });
      expect(result!.scoreResults![0].itemIdentifiers![2]).toEqual({
        name: 'Report ID',
        value: 'RPT-789',
        url: '/reports/789'
      });
    });

    it('should handle legacy JSON string identifiers', () => {
      const legacyIdentifiers = JSON.stringify([
        { name: 'Legacy Form ID', id: 'LEG-123' },
        { name: 'Legacy Session', id: 'SESS-OLD', url: '/legacy/session' }
      ]);

      const mockEvaluation: BaseEvaluation = {
        id: 'eval-2',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        scoreResults: {
          items: [{
            id: 'result-1',
            value: 'positive',
            confidence: 0.8,
            metadata: {},
            explanation: null,
            trace: null,
            itemId: 'item-1',
            createdAt: '2024-01-01T00:00:00Z',
            item: {
              id: 'item-1',
              externalId: 'ext-1',
              identifiers: legacyIdentifiers,
              itemIdentifiers: null // No modern identifiers
            }
          }]
        }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      expect(result!.scoreResults![0].itemIdentifiers).toHaveLength(2);
      expect(result!.scoreResults![0].itemIdentifiers![0]).toEqual({
        name: 'Legacy Form ID',
        value: 'LEG-123'
      });
      expect(result!.scoreResults![0].itemIdentifiers![1]).toEqual({
        name: 'Legacy Session',
        value: 'SESS-OLD',
        url: '/legacy/session'
      });
    });

    it('should parse JSON metadata and extract human_label', () => {
      const jsonMetadata = JSON.stringify({
        human_label: 'correct_answer',
        correct: true,
        human_explanation: 'This is the right answer',
        text: 'Sample input text'
      });

      const mockEvaluation: BaseEvaluation = {
        id: 'eval-metadata',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        scoreResults: {
          items: [{
            id: 'result-metadata',
            value: 'positive',
            confidence: 0.9,
            metadata: jsonMetadata, // JSON string metadata
            explanation: null,
            trace: null,
            itemId: 'item-metadata',
            createdAt: '2024-01-01T00:00:00Z'
          }]
        }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      expect(result!.scoreResults![0].metadata).toEqual({
        human_label: 'correct_answer',
        correct: true,
        human_explanation: 'This is the right answer',
        text: 'Sample input text'
      });
    });

    it('should handle double-encoded JSON metadata', () => {
      const innerJson = JSON.stringify({
        human_label: 'nested_answer',
        correct: false
      });
      const doubleEncodedMetadata = JSON.stringify(innerJson);

      const mockEvaluation: BaseEvaluation = {
        id: 'eval-double',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        scoreResults: {
          items: [{
            id: 'result-double',
            value: 'negative',
            confidence: 0.7,
            metadata: doubleEncodedMetadata, // Double-encoded JSON
            explanation: null,
            trace: null,
            itemId: 'item-double',
            createdAt: '2024-01-01T00:00:00Z'
          }]
        }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      expect(result!.scoreResults![0].metadata.human_label).toBe('nested_answer');
      expect(result!.scoreResults![0].metadata.correct).toBe(false);
    });

    it('should handle nested results structure in metadata', () => {
      const nestedMetadata = {
        results: {
          'first_result': {
            value: 'predicted_value',
            metadata: {
              human_label: 'nested_human_label',
              correct: true
            }
          }
        },
        human_label: 'top_level_label'
      };

      const mockEvaluation: BaseEvaluation = {
        id: 'eval-nested',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        scoreResults: {
          items: [{
            id: 'result-nested',
            value: 'positive',
            confidence: 0.8,
            metadata: nestedMetadata,
            explanation: null,
            trace: null,
            itemId: 'item-nested',
            createdAt: '2024-01-01T00:00:00Z'
          }]
        }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      // Should prefer nested metadata over top-level
      expect(result!.scoreResults![0].metadata.human_label).toBe('nested_human_label');
      expect(result!.scoreResults![0].metadata.correct).toBe(true);
    });

    it('should prefer modern itemIdentifiers over legacy identifiers', () => {
      const legacyIdentifiers = JSON.stringify([
        { name: 'Legacy ID', id: 'OLD-123' }
      ]);

      const mockEvaluation: BaseEvaluation = {
        id: 'eval-3',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        scoreResults: {
          items: [{
            id: 'result-1',
            value: 'positive',
            confidence: 0.9,
            metadata: {},
            explanation: null,
            trace: null,
            itemId: 'item-1',
            createdAt: '2024-01-01T00:00:00Z',
            item: {
              id: 'item-1',
              externalId: 'ext-1',
              identifiers: legacyIdentifiers,
              itemIdentifiers: {
                items: [
                  { name: 'Modern ID', value: 'NEW-456', position: 1, url: null }
                ]
              }
            }
          }]
        }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      expect(result!.scoreResults![0].itemIdentifiers).toHaveLength(1);
      expect(result!.scoreResults![0].itemIdentifiers![0]).toEqual({
        name: 'Modern ID',
        value: 'NEW-456'
      });
    });

    it('should handle score results without item relationships', () => {
      const mockEvaluation: BaseEvaluation = {
        id: 'eval-4',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        scoreResults: {
          items: [{
            id: 'result-1',
            value: 'positive',
            confidence: 0.8,
            metadata: {},
            explanation: null,
            trace: null,
            itemId: 'item-1',
            createdAt: '2024-01-01T00:00:00Z'
            // No item relationship
          }]
        }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      expect(result!.scoreResults![0].itemIdentifiers).toBeNull();
    });

    it('should handle evaluations with no score results', () => {
      const mockEvaluation: BaseEvaluation = {
        id: 'eval-5',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'RUNNING',
        accountId: 'account-1',
        scoreResults: null
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      expect(result!.scoreResults).toEqual([]);
    });

    it('should handle empty score results array', () => {
      const mockEvaluation: BaseEvaluation = {
        id: 'eval-6',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        scoreResults: { items: [] }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      expect(result!.scoreResults).toEqual([]);
    });
  });

  describe('golden path data flow', () => {
    it('should preserve all score result fields including itemIdentifiers', () => {
      const mockEvaluation: BaseEvaluation = {
        id: 'eval-golden',
        type: 'accuracy',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: '2024-01-01T00:00:00Z',
        status: 'COMPLETED',
        accountId: 'account-1',
        accuracy: 0.92,
        scoreResults: {
          items: [{
            id: 'result-golden',
            value: 'positive',
            confidence: 0.95,
            metadata: { human_label: 'correct', correct: true },
            explanation: 'High confidence prediction',
            trace: { model: 'gpt-4' },
            itemId: 'item-golden',
            createdAt: '2024-01-01T00:00:00Z',
            feedbackItem: {
              editCommentValue: 'Good prediction'
            },
            item: {
              id: 'item-golden',
              externalId: 'ext-golden',
              identifiers: null,
              itemIdentifiers: {
                items: [
                  { name: 'Form ID', value: 'GOLDEN-FORM', position: 1, url: null },
                  { name: 'User ID', value: 'USER-123', position: 2, url: '/users/123' }
                ]
              }
            }
          }]
        }
      } as any;

      const result = transformEvaluation(mockEvaluation);
      
      expect(result).toBeTruthy();
      const scoreResult = result!.scoreResults![0];
      
      // Verify all fields are preserved
      expect(scoreResult.id).toBe('result-golden');
      expect(scoreResult.value).toBe('positive');
      expect(scoreResult.confidence).toBe(0.95);
      expect(scoreResult.explanation).toBe('High confidence prediction');
      expect(scoreResult.trace).toEqual({ model: 'gpt-4' });
      expect(scoreResult.itemId).toBe('item-golden');
      expect(scoreResult.feedbackItem).toEqual({ editCommentValue: 'Good prediction' });
      
      // Verify metadata is properly structured
      expect(scoreResult.metadata).toEqual({
        human_label: 'correct',
        correct: true,
        human_explanation: null,
        text: null
      });
      
      // Verify itemIdentifiers are correctly extracted and preserved
      expect(scoreResult.itemIdentifiers).toHaveLength(2);
      expect(scoreResult.itemIdentifiers![0]).toEqual({
        name: 'Form ID',
        value: 'GOLDEN-FORM'
      });
      expect(scoreResult.itemIdentifiers![1]).toEqual({
        name: 'User ID',
        value: 'USER-123',
        url: '/users/123'
      });
    });
  });
});