// Mock for aws-amplify/data in Storybook

export const generateClient = () => ({
  models: {
    Account: {
      list: async () => ({
        data: [
          {
            id: 'mock-account-1',
            key: 'call-criteria',
            name: 'Mock Account',
            settings: null,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
          }
        ]
      })
    },
    ChatMessage: {
      list: async ({ filter }: any) => {
        // Return mock messages that match the accountId filter
        const mockMessages = [
          {
            id: 'msg-1',
            content: 'This is a notification message from a procedure',
            role: 'SYSTEM',
            messageType: 'MESSAGE',
            humanInteraction: 'NOTIFICATION',
            accountId: 'mock-account-1',
            procedureId: 'proc-123',
            createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
          },
          {
            id: 'msg-2',
            content: 'Warning: Low accuracy detected on score evaluation',
            role: 'SYSTEM',
            messageType: 'MESSAGE',
            humanInteraction: 'ALERT_WARNING',
            accountId: 'mock-account-1',
            procedureId: 'proc-123',
            createdAt: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
          },
          {
            id: 'msg-3',
            content: 'Evaluation completed successfully for CS3 Services v2',
            role: 'ASSISTANT',
            messageType: 'MESSAGE',
            humanInteraction: 'CHAT_ASSISTANT',
            accountId: 'mock-account-1',
            procedureId: 'proc-456',
            createdAt: new Date(Date.now() - 1 * 60 * 1000).toISOString(),
          },
          {
            id: 'msg-4',
            content: 'Critical error: Failed to connect to database',
            role: 'SYSTEM',
            messageType: 'MESSAGE',
            humanInteraction: 'ALERT_CRITICAL',
            accountId: 'mock-account-1',
            procedureId: 'proc-789',
            createdAt: new Date().toISOString(),
          },
        ];

        // Filter by accountId if provided
        if (filter?.accountId?.eq) {
          return {
            data: mockMessages.filter(msg => msg.accountId === filter.accountId.eq)
          };
        }

        return { data: mockMessages };
      },
      onCreate: () => ({
        subscribe: ({ next, error }: any) => {
          // Simulate a new message after 3 seconds
          const timeout = setTimeout(() => {
            if (next) {
              next({
                id: 'msg-new',
                content: 'New message arrived!',
                role: 'SYSTEM',
                messageType: 'MESSAGE',
                humanInteraction: 'NOTIFICATION',
                createdAt: new Date().toISOString(),
              });
            }
          }, 3000);

          return {
            unsubscribe: () => clearTimeout(timeout)
          };
        }
      })
    }
  }
});
