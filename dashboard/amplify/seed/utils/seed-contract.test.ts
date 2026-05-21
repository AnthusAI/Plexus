import { existsSync, readFileSync } from 'node:fs';
import { loadConfig } from '../config';
import { buildCreateInput, getPrimaryKeyInput, getSeedItemLabel, SkippedSeedItemError } from './create-input';
import { findAccountIndexQueryName } from './model-queries';

const outputsUrl = new URL('../../../amplify_outputs.json', import.meta.url);
const hasAmplifyOutputs = existsSync(outputsUrl);
const outputs = hasAmplifyOutputs
  ? JSON.parse(readFileSync(outputsUrl, { encoding: 'utf8' }))
  : null;

(hasAmplifyOutputs ? describe : describe.skip)('sandbox seed contract', () => {
  it('configures account-scoped copy only for models that have accountId', async () => {
    const config = await loadConfig();
    const missingAccountId: string[] = [];

    for (const table of Object.values(config.tables)) {
      if (table.name === 'Account' || table.gsiKey !== 'accountId') {
        continue;
      }

      if (!outputs.data.model_introspection.models[table.name]?.fields.accountId) {
        missingAccountId.push(table.name);
      }
    }

    expect(missingAccountId).toEqual([]);
  });

  it('finds exact and sorted account index generated query names', () => {
    expect(findAccountIndexQueryName({
      listScoringJobByAccountId: jest.fn()
    }, 'ScoringJob')).toBe('listScoringJobByAccountId');

    expect(findAccountIndexQueryName({
      listTaskByAccountIdAndUpdatedAt: jest.fn()
    }, 'Task')).toBe('listTaskByAccountIdAndUpdatedAt');

    expect(findAccountIndexQueryName({
      listDataSourceByAccountIdAndKey: jest.fn(),
      listDataSourceByAccountIdAndUpdatedAt: jest.fn()
    }, 'DataSource')).toBe('listDataSourceByAccountIdAndKey');
  });

  it('documents parent-scoped tables that require traversal from copied parent ids', () => {
    const parentScopedTables = [
      'ScorecardSection',
      'Score',
      'ScoreVersion',
      'DataSourceVersion',
      'TaskStage',
      'ReportBlock',
      'ScorecardExampleItem'
    ];
    const missingModels = parentScopedTables.filter((tableName) => !outputs.data.model_introspection.models[tableName]);

    expect(missingModels).toEqual([]);
  });

  it('keeps every enabled table bounded by default', async () => {
    const config = await loadConfig();
    const unboundedTables = Object.values(config.tables)
      .filter((table) => table.enabled !== false)
      .filter((table) => typeof table.maxItems !== 'number' || table.maxItems <= 0)
      .map((table) => table.name);

    expect(unboundedTables).toEqual([]);
  });

  it('caps high-volume tables to development-sized samples', async () => {
    const config = await loadConfig();

    expect(config.tables['Procedure'].maxItems).toBeLessThanOrEqual(12);
    expect(config.tables['Evaluation'].maxItems).toBeLessThanOrEqual(250);
    expect(config.tables['AggregatedMetrics'].maxItems).toBeLessThanOrEqual(250);
    expect(config.tables['ChatSession'].maxItems).toBeLessThanOrEqual(25);
    expect(config.tables['ChatMessage'].maxItems).toBeLessThanOrEqual(250);
    expect(config.tables['ScoreVersion'].maxPerParent).toBeLessThanOrEqual(3);
    expect(config.tables['ScoreVersion'].preferFeatured).toBe(true);
  });

  it('keeps sampled table requested counts within their hard caps', async () => {
    const config = await loadConfig();
    const overRequestedTables = Object.values(config.tables)
      .filter((table) => table.strategy === 'sampled')
      .filter((table) => (table.recentCount || 0) + (table.sampleCount || 0) > (table.maxItems || 0))
      .map((table) => table.name);

    expect(overRequestedTables).toEqual([]);
  });

  it('normalizes historical ScoreVersion rows with null isFeatured', () => {
    const input = buildCreateInput('ScoreVersion', {
      id: 'version-1',
      scoreId: 'score-1',
      configuration: '{}',
      createdAt: '2024-01-01T00:00:00.000Z',
      updatedAt: '2024-01-01T00:00:00.000Z',
      isFeatured: null
    });

    expect(input).toMatchObject({
      id: 'version-1',
      scoreId: 'score-1',
      configuration: '{}',
      isFeatured: 'false'
    });
    expect(input).not.toHaveProperty('createdAt');
    expect(input).not.toHaveProperty('updatedAt');
  });

  it('normalizes historical ScoreResult rows that predate status', () => {
    const input = buildCreateInput('ScoreResult', {
      id: 'result-1',
      value: 'yes',
      type: 'prediction',
      itemId: 'item-1',
      accountId: 'account-1',
      scorecardId: 'scorecard-1',
      scoreId: 'score-1',
      status: null
    });

    expect(input).toMatchObject({
      id: 'result-1',
      type: 'prediction',
      status: 'UNKNOWN'
    });
  });

  it('skips historical ScoreResult rows that cannot satisfy composite score indexes', () => {
    expect(() => buildCreateInput('ScoreResult', {
      id: 'result-1',
      value: 'yes',
      type: 'prediction',
      status: 'UNKNOWN',
      itemId: 'item-1',
      accountId: 'account-1',
      scorecardId: 'scorecard-1'
    })).toThrow(SkippedSeedItemError);
  });

  it('uses custom primary keys for AggregatedMetrics idempotency and labels', () => {
    const input = buildCreateInput('AggregatedMetrics', {
      accountId: 'account-1',
      compositeKey: 'metric-key',
      recordType: 'score',
      timeRangeStart: '2024-01-01T00:00:00.000Z',
      timeRangeEnd: '2024-01-01T01:00:00.000Z',
      numberOfMinutes: 60,
      count: 1,
      complete: true
    });

    expect(getPrimaryKeyInput('AggregatedMetrics', input)).toEqual({
      accountId: 'account-1',
      compositeKey: 'metric-key'
    });
    expect(getSeedItemLabel('AggregatedMetrics', input)).toBe('account-1/metric-key');
  });

  it('rejects create inputs that are missing required fields', () => {
    expect(() => buildCreateInput('Scorecard', {
      id: 'scorecard-1',
      key: 'scorecard-key',
      accountId: 'account-1'
    })).toThrow('Required fields are null or missing: name');
  });
});
