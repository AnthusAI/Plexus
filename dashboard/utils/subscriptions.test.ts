import { observeRecentTasks, observeRecentEvaluations, observeScoreResults } from './subscriptions';
import { getClient } from './amplify-client';
import type { Schema } from '../amplify/data/resource';

// Mock the Amplify client
jest.mock('./amplify-client', () => ({
  getClient: jest.fn()
}));

// Mock the transformers
jest.mock('./transformers', () => ({
  convertToAmplifyTask: jest.fn(data => ({ ...data, type: 'converted' })),
  processTask: jest.fn(task => Promise.resolve({ ...task, type: 'processed' }))
}));

describe('subscriptions', () => {
  let mockClient: any;
  let mockSubscribe: jest.Mock;
  let mockUnsubscribe: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();

    mockUnsubscribe = jest.fn();
    mockSubscribe = jest.fn(() => ({ unsubscribe: mockUnsubscribe }));

    mockClient = {
      graphql: jest.fn(() => ({
        subscribe: mockSubscribe
      })),
      models: {
        Task: {
          list: jest.fn()
        },
        Account: {
          list: jest.fn()
        },
        ScoreResult: {
          listScoreResultByEvaluationId: jest.fn(),
          onCreate: jest.fn(() => ({ subscribe: mockSubscribe })),
          onUpdate: jest.fn(() => ({ subscribe: mockSubscribe })),
          onDelete: jest.fn(() => ({ subscribe: mockSubscribe }))
        }
      }
    };

    (getClient as jest.Mock).mockReturnValue(mockClient);
  });

  describe('observeRecentTasks', () => {
    it('sets up a subscription for task updates', () => {
      const handler = {
        next: jest.fn(),
        error: jest.fn()
      };

      const subscription = observeRecentTasks();
      subscription.subscribe(handler);

      expect(mockClient.graphql).toHaveBeenCalledWith({
        query: expect.any(String)
      });
      expect(mockSubscribe).toHaveBeenCalled();
    });

    it('handles task update events', (done) => {
      const handler = {
        next: jest.fn((data) => {
          expect(data).toEqual({
            data: expect.objectContaining({
              type: 'processed'
            })
          });
          done();
        }),
        error: jest.fn((error) => done(error))
      };

      const subscription = observeRecentTasks();
      subscription.subscribe(handler);

      const mockTaskUpdate = {
        data: {
          onUpdateTask: {
            id: 'task123',
            status: 'COMPLETED'
          }
        }
      };

      // Get the subscription handler and call it with mock data
      const subscriptionHandler = mockSubscribe.mock.calls[0][0];
      subscriptionHandler.next(mockTaskUpdate);
    });

    it('handles subscription errors', () => {
      const handler = {
        next: jest.fn(),
        error: jest.fn()
      };

      const subscription = observeRecentTasks();
      subscription.subscribe(handler);

      const error = new Error('Subscription error');
      const subscriptionHandler = mockSubscribe.mock.calls[0][0];
      subscriptionHandler.error(error);

      expect(handler.error).toHaveBeenCalledWith(error);
    });
  });

  describe('observeRecentEvaluations', () => {
    beforeEach(() => {
      // Mock successful account lookup
      mockClient.models.Account.list.mockResolvedValue({
        data: [{ id: 'acc123' }]
      });

      // Mock successful evaluations query
      mockClient.graphql.mockImplementation(() => ({
        subscribe: mockSubscribe,
        data: {
          listEvaluationByAccountIdAndUpdatedAt: {
            items: [{
              id: 'eval123',
              type: 'test'
            }]
          }
        }
      }));
    });

    it('sets up a subscription for evaluation updates', (done) => {
      const subscription = observeRecentEvaluations();
      
      subscription.subscribe({
        next: (data) => {
          expect(data.items).toBeDefined();
          expect(data.isSynced).toBe(true);
          done();
        },
        error: done
      });

      expect(mockClient.graphql).toHaveBeenCalled();
      expect(mockSubscribe).toHaveBeenCalled();
    });

    it('handles evaluation update events', (done) => {
      const subscription = observeRecentEvaluations();
      
      subscription.subscribe({
        next: (data) => {
          if (data.items.length > 0) {
            expect(data.items[0].id).toBe('eval123');
            done();
          }
        },
        error: done
      });

      // Simulate an evaluation update
      const mockUpdate = {
        data: {
          onUpdateEvaluation: {
            id: 'eval123',
            type: 'updated'
          }
        }
      };

      const subscriptionHandler = mockSubscribe.mock.calls[0][0];
      subscriptionHandler.next(mockUpdate);
    });

    it('handles subscription errors', (done) => {
      const subscription = observeRecentEvaluations();
      
      subscription.subscribe({
        next: () => {},
        error: (error) => {
          expect(error.message).toBe('Subscription error');
          done();
        }
      });

      const error = new Error('Subscription error');
      const subscriptionHandler = mockSubscribe.mock.calls[0][0];
      subscriptionHandler.error(error);
    });
  });

  describe('observeScoreResults', () => {
    beforeEach(() => {
      mockClient.models.ScoreResult.listScoreResultByEvaluationId.mockResolvedValue({
        data: [{
          id: 'score123',
          value: 0.9
        }]
      });
    });

    it('sets up subscriptions for score result changes', () => {
      const handler = {
        next: jest.fn(),
        error: jest.fn()
      };

      const subscription = observeScoreResults('eval123');
      subscription.subscribe(handler);

      // Should set up onCreate, onUpdate, and onDelete subscriptions
      expect(mockClient.models.ScoreResult.onCreate).toHaveBeenCalled();
      expect(mockClient.models.ScoreResult.onUpdate).toHaveBeenCalled();
      expect(mockClient.models.ScoreResult.onDelete).toHaveBeenCalled();
    });

    it('fetches initial score results', (done) => {
      const subscription = observeScoreResults('eval123');
      
      subscription.subscribe({
        next: (data) => {
          expect(data.items).toHaveLength(1);
          expect(data.items[0].id).toBe('score123');
          done();
        },
        error: done
      });
    });

    it('handles subscription cleanup', () => {
      const subscription = observeScoreResults('eval123');
      const { unsubscribe } = subscription.subscribe({
        next: jest.fn(),
        error: jest.fn()
      });

      unsubscribe();

      // Should have called unsubscribe for all three subscriptions
      expect(mockUnsubscribe).toHaveBeenCalledTimes(3);
    });
  });
}); 