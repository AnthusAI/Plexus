import { convertToAmplifyTask, processTask } from './transformers';
import type { AmplifyTask, ProcessedTask } from './data-operations';

describe('transformers', () => {
  describe('convertToAmplifyTask', () => {
    it('converts raw data to AmplifyTask with basic fields', () => {
      const rawData = {
        id: 'test-id',
        command: 'test-command',
        type: 'test-type',
        status: 'PENDING',
        target: 'test-target',
        description: 'test description',
        metadata: { key: 'value' },
        createdAt: '2024-01-01T00:00:00Z'
      };

      const result = convertToAmplifyTask(rawData);

      expect(result.id).toBe(rawData.id);
      expect(result.command).toBe(rawData.command);
      expect(result.type).toBe(rawData.type);
      expect(result.status).toBe(rawData.status);
      expect(result.target).toBe(rawData.target);
      expect(result.description).toBe(rawData.description);
      expect(result.metadata).toEqual(rawData.metadata);
      expect(result.createdAt).toBe(rawData.createdAt);
    });

    it('creates lazy loaders for nested objects', () => {
      const rawData = {
        id: 'test-id',
        stages: {
          items: [{
            id: 'stage-1',
            name: 'Stage 1',
            order: 1,
            status: 'PENDING'
          }]
        },
        scorecard: {
          id: 'scorecard-1',
          name: 'Scorecard 1'
        },
        score: {
          id: 'score-1',
          name: 'Score 1'
        }
      };

      const result = convertToAmplifyTask(rawData);

      expect(typeof result.stages).toBe('function');
      expect(typeof result.scorecard).toBe('function');
      expect(typeof result.score).toBe('function');
    });

    it('handles missing optional fields', () => {
      const rawData = {
        id: 'test-id',
        command: 'test-command',
        type: 'test-type',
        status: 'PENDING',
        target: 'test-target'
      };

      const result = convertToAmplifyTask(rawData);

      expect(result.description).toBeNull();
      expect(result.metadata).toBeUndefined();
      expect(result.stages).toBeUndefined();
      expect(result.scorecard).toBeUndefined();
      expect(result.score).toBeUndefined();
    });
  });

  describe('processTask', () => {
    it('processes an AmplifyTask into a ProcessedTask with basic fields', async () => {
      const amplifyTask: AmplifyTask = {
        id: 'test-id',
        command: 'test-command',
        type: 'test-type',
        status: 'PENDING',
        target: 'test-target',
        description: 'test description',
        metadata: { key: 'value' },
        createdAt: '2024-01-01T00:00:00Z'
      };

      const result = await processTask(amplifyTask);

      expect(result.id).toBe(amplifyTask.id);
      expect(result.command).toBe(amplifyTask.command);
      expect(result.type).toBe(amplifyTask.type);
      expect(result.status).toBe(amplifyTask.status);
      expect(result.target).toBe(amplifyTask.target);
      expect(result.description).toBe(amplifyTask.description);
      expect(result.metadata).toEqual(amplifyTask.metadata);
      expect(result.createdAt).toBe(amplifyTask.createdAt);
      expect(result.stages).toEqual([]);
    });

    it('processes stages from a function loader', async () => {
      const amplifyTask: AmplifyTask = {
        id: 'test-id',
        command: 'test-command',
        type: 'test-type',
        status: 'PENDING',
        target: 'test-target',
        stages: () => Promise.resolve({
          data: {
            items: [{
              id: 'stage-1',
              name: 'Stage 1',
              order: 1,
              status: 'PENDING'
            }]
          }
        })
      };

      const result = await processTask(amplifyTask);

      expect(result.stages).toHaveLength(1);
      expect(result.stages[0].id).toBe('stage-1');
      expect(result.stages[0].name).toBe('Stage 1');
      expect(result.stages[0].order).toBe(1);
      expect(result.stages[0].status).toBe('PENDING');
    });

    it('processes stages from direct data', async () => {
      const amplifyTask: AmplifyTask = {
        id: 'test-id',
        command: 'test-command',
        type: 'test-type',
        status: 'PENDING',
        target: 'test-target',
        stages: {
          data: {
            items: [{
              id: 'stage-1',
              name: 'Stage 1',
              order: 1,
              status: 'PENDING'
            }]
          }
        }
      };

      const result = await processTask(amplifyTask);

      expect(result.stages).toHaveLength(1);
      expect(result.stages[0].id).toBe('stage-1');
      expect(result.stages[0].name).toBe('Stage 1');
      expect(result.stages[0].order).toBe(1);
      expect(result.stages[0].status).toBe('PENDING');
    });

    it('handles string metadata', async () => {
      const amplifyTask: AmplifyTask = {
        id: 'test-id',
        command: 'test-command',
        type: 'test-type',
        status: 'PENDING',
        target: 'test-target',
        metadata: '{"key":"value"}'
      };

      const result = await processTask(amplifyTask);

      expect(result.metadata).toEqual({ key: 'value' });
    });

    it('handles invalid string metadata', async () => {
      const amplifyTask: AmplifyTask = {
        id: 'test-id',
        command: 'test-command',
        type: 'test-type',
        status: 'PENDING',
        target: 'test-target',
        metadata: 'invalid-json'
      };

      const result = await processTask(amplifyTask);

      expect(result.metadata).toBeNull();
    });
  });
}); 