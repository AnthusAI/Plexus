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
    jest.useFakeTimers();

    mockUnsubscribe = jest.fn();
    mockSubscribe = jest.fn(() => ({ unsubscribe: mockUnsubscribe }));

    // Mock the GraphQL client with proper subscription support
    mockClient = {
      graphql: jest.fn((options: any) => {
        // If it's a subscription query, return a subscribable
        if (options.query.includes('subscription')) {
          return {
            subscribe: mockSubscribe
          };
        }
        // Otherwise return the data response
        return Promise.resolve({
          data: {
            listEvaluationByAccountIdAndUpdatedAt: {
              items: [{
                id: 'eval123',
                type: 'test'
              }]
            }
          }
        });
      }),
      models: {
        Task: {
          list: jest.fn()
        },
        Account: {
          list: jest.fn(() => Promise.resolve({
            data: [{ id: 'acc123', key: 'call-criteria' }]
          }))
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

  afterEach(() => {
    jest.useRealTimers();
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
    it('sets up a subscription for evaluation updates', (done) => {
      const subscription = observeRecentEvaluations();
      
      // Set up the mock to resolve the initial data load
      mockClient.graphql.mockImplementationOnce(() => ({
        data: {
          listEvaluationByAccountIdAndUpdatedAt: {
            items: [{
              id: 'eval123',
              type: 'test'
            }]
          }
        }
      }));

      let dataReceived = false;
      
      subscription.subscribe({
        next: (data) => {
          expect(data.items).toBeDefined();
          expect(data.isSynced).toBe(true);
          expect(data.items).toHaveLength(1);
          expect(data.items[0].id).toBe('eval123');
          
          if (!dataReceived) {
            dataReceived = true;
            done();
          }
        },
        error: (error) => {
          done(error);
        }
      });
    });

    it('handles evaluation update events', (done) => {
      const mockUpdate = {
        data: {
          onUpdateEvaluation: {
            id: 'eval123',
            type: 'updated'
          }
        }
      };

      // Mock the account lookup
      mockClient.models.Account.list.mockResolvedValueOnce({
        data: [{ id: 'acc123', key: 'call-criteria' }]
      });

      // Set up the mock to resolve the initial data load
      mockClient.graphql.mockImplementation((options: any) => {
        if (options.query.includes('listEvaluationByAccountIdAndUpdatedAt')) {
          return Promise.resolve({
            data: {
              listEvaluationByAccountIdAndUpdatedAt: {
                items: [{
                  id: 'eval123',
                  type: 'test'
                }]
              }
            }
          });
        }
        if (options.query.includes('subscription')) {
          return {
            subscribe: mockSubscribe
          };
        }
        return Promise.resolve({ data: null });
      });

      // Set up the subscription mock
      mockSubscribe.mockImplementation((handler: any) => {
        // Immediately trigger the update event
        handler.next(mockUpdate);
        return { unsubscribe: mockUnsubscribe };
      });

      const subscription = observeRecentEvaluations();
      let initialDataReceived = false;

      subscription.subscribe({
        next: (data) => {
          if (!initialDataReceived) {
            initialDataReceived = true;
            expect(data.items).toHaveLength(1);
            expect(data.items[0].id).toBe('eval123');
            expect(data.items[0].type).toBe('test');
          } else {
            expect(data.items[0].type).toBe('updated');
            done();
          }
        },
        error: (error) => {
          console.error('Test error:', error);
          done(error);
        }
      });
    }, 10000); // Increase timeout to 10 seconds

    it('handles subscription errors', (done) => {
      const subscription = observeRecentEvaluations();
      
      // Set up the mock to reject the initial data load
      mockClient.models.Account.list.mockRejectedValueOnce(new Error('Subscription error'));

      subscription.subscribe({
        next: () => {
          done(new Error('Should not receive data after error'));
        },
        error: (error) => {
          expect(error.message).toBe('Subscription error');
          done();
        }
      });
    });

    it('cleans up subscriptions on unsubscribe', (done) => {
      let resolveSubscriptionSetup: () => void;
      const subscriptionSetup = new Promise<void>((resolve) => {
        resolveSubscriptionSetup = resolve;
      });

      mockSubscribe.mockImplementation(() => {
        resolveSubscriptionSetup();
        return { unsubscribe: mockUnsubscribe };
      });

      const subscription = observeRecentEvaluations();
      const sub = subscription.subscribe({
        next: async (data) => {
          try {
            if (data.isSynced) {
              await subscriptionSetup;
              sub.unsubscribe();
              expect(mockUnsubscribe).toHaveBeenCalled();
              done();
            }
          } catch (error) {
            done(error);
          }
        },
        error: (error) => {
          console.error('Test error:', error);
          done(error);
        }
      });
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