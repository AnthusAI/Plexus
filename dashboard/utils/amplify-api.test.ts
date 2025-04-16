import { listFromModel, getFromModel, createTask, updateTask } from './amplify-api';
import { getClient } from './amplify-client';
import type { AmplifyTask, ProcessedTask } from './data-operations';

// Mock the Amplify client
jest.mock('./amplify-client', () => ({
  getClient: jest.fn()
}));

// Mock the transformers
jest.mock('./transformers', () => ({
  convertToAmplifyTask: jest.fn(data => ({ ...data, type: 'converted' })),
  processTask: jest.fn(task => Promise.resolve({ ...task, type: 'processed' }))
}));

describe('amplify-api', () => {
  let mockClient: any;

  beforeEach(() => {
    // Reset all mocks
    jest.clearAllMocks();

    // Create a mock client
    mockClient = {
      models: {
        Task: {
          list: jest.fn(),
          get: jest.fn(),
          create: jest.fn(),
          update: jest.fn()
        }
      }
    };

    // Set up the mock client
    (getClient as jest.Mock).mockReturnValue(mockClient);
  });

  describe('listFromModel', () => {
    it('lists items from a model with default options', async () => {
      const mockData = [{ id: '1', name: 'Test' }];
      mockClient.models.Task.list.mockResolvedValue({
        data: mockData,
        nextToken: null
      });

      const result = await listFromModel('Task');

      expect(mockClient.models.Task.list).toHaveBeenCalledWith({
        include: ['stages', 'scorecard', 'score']
      });
      expect(result).toEqual({
        data: mockData,
        nextToken: undefined
      });
    });

    it('handles list errors gracefully', async () => {
      mockClient.models.Task.list.mockRejectedValue(new Error('Test error'));

      const result = await listFromModel('Task');

      expect(result).toEqual({ data: [] });
    });

    it('passes through filter options', async () => {
      const options = {
        limit: 10,
        filter: { status: 'ACTIVE' },
        nextToken: 'token123',
        sortDirection: 'DESC' as const
      };

      await listFromModel('Task', options);

      expect(mockClient.models.Task.list).toHaveBeenCalledWith({
        ...options,
        include: ['stages', 'scorecard', 'score']
      });
    });
  });

  describe('getFromModel', () => {
    it('gets an item by id', async () => {
      const mockData = { id: '1', name: 'Test' };
      mockClient.models.Task.get.mockResolvedValue({
        data: mockData
      });

      const result = await getFromModel('Task', '1');

      expect(mockClient.models.Task.get).toHaveBeenCalledWith({ id: '1' });
      expect(result).toEqual({ data: { ...mockData, type: 'converted' } });
    });

    it('handles get errors gracefully', async () => {
      mockClient.models.Task.get.mockRejectedValue(new Error('Test error'));

      const result = await getFromModel('Task', '1');

      expect(result).toEqual({ data: null });
    });
  });

  describe('createTask', () => {
    it('creates a task with the given input', async () => {
      const input: Omit<AmplifyTask, 'id' | 'createdAt' | 'updatedAt'> & { accountId: string } = {
        accountId: 'acc123',
        command: 'test',
        type: 'test',
        status: 'PENDING',
        target: 'test'
      };

      const mockResponse = {
        data: { ...input, id: 'task123' }
      };

      mockClient.models.Task.create.mockResolvedValue(mockResponse);

      const result = await createTask(input);

      expect(mockClient.models.Task.create).toHaveBeenCalledWith({
        ...input,
        createdAt: expect.any(String)
      });
      expect(result).toEqual({ ...mockResponse.data, type: 'processed' });
    });

    it('handles create errors gracefully', async () => {
      mockClient.models.Task.create.mockRejectedValue(new Error('Test error'));

      const result = await createTask({
        accountId: 'acc123',
        command: 'test',
        type: 'test',
        status: 'PENDING',
        target: 'test'
      });

      expect(result).toBeNull();
    });
  });

  describe('updateTask', () => {
    it('updates a task with the given input', async () => {
      const input: Partial<AmplifyTask> = {
        status: 'COMPLETED'
      };

      const mockResponse = {
        data: { id: 'task123', ...input }
      };

      mockClient.models.Task.update.mockResolvedValue(mockResponse);

      const result = await updateTask('task123', input);

      expect(mockClient.models.Task.update).toHaveBeenCalledWith({
        id: 'task123',
        ...input
      });
      expect(result).toEqual({ ...mockResponse.data, type: 'processed' });
    });

    it('handles update errors gracefully', async () => {
      mockClient.models.Task.update.mockRejectedValue(new Error('Test error'));

      const result = await updateTask('task123', { status: 'COMPLETED' });

      expect(result).toBeNull();
    });

    it('throws error for invalid model name', async () => {
      const result = await updateTask('task123', { status: 'COMPLETED' }, 'InvalidModel' as any);

      expect(result).toBeNull();
    });
  });
}); 