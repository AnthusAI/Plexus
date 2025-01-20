import { describe, it, expect, jest } from '@jest/globals'
import type { Schema } from '@/amplify/data/resource'

type MockDataset = Pick<Schema['Dataset']['type'], 'id' | 'name' | 'description' | 'scorecardId' | 'scoreId' | 'currentVersionId' | 'createdAt' | 'updatedAt'>
type MockDatasetVersion = Pick<Schema['DatasetVersion']['type'], 'id' | 'datasetId' | 'versionNumber' | 'configuration' | 'createdAt'>
type MockDatasetProfile = Pick<Schema['DatasetProfile']['type'], 'id' | 'datasetId' | 'datasetVersionId' | 'columnList' | 'recordCounts' | 'answerDistribution' | 'createdAt'>

// Mock data
const mockDataset: MockDataset = {
  id: 'test-dataset-id',
  name: 'Test Dataset',
  description: 'Test Description',
  scorecardId: 'test-scorecard',
  scoreId: 'test-score',
  currentVersionId: null,
  createdAt: '2024-01-01T00:00:00.000Z',
  updatedAt: '2024-01-01T00:00:00.000Z',
}

const mockVersion: MockDatasetVersion = {
  id: 'test-version-id',
  datasetId: 'test-dataset-id',
  versionNumber: 1,
  configuration: { type: 'test' },
  createdAt: '2024-01-01T00:00:00.000Z',
}

const mockProfile: MockDatasetProfile = {
  id: 'test-profile-id',
  datasetId: 'test-dataset-id',
  datasetVersionId: 'test-version-id',
  columnList: ['col1', 'col2'],
  recordCounts: { total: 100 },
  answerDistribution: { yes: 60, no: 40 },
  createdAt: '2024-01-01T00:00:00.000Z',
}

// Mock factory function
const createMockAmplifyClient = () => ({
  Dataset: {
    create: jest.fn<any>().mockResolvedValue({ data: mockDataset }),
    update: jest.fn<any>().mockResolvedValue({ data: { ...mockDataset, currentVersionId: mockVersion.id } }),
    get: jest.fn<any>().mockResolvedValue({ data: { ...mockDataset, currentVersionId: mockVersion.id } }),
  },
  DatasetVersion: {
    create: jest.fn<any>().mockResolvedValue({ data: mockVersion }),
    list: jest.fn<any>().mockResolvedValue({ data: [mockVersion, { ...mockVersion, id: 'test-version-id-2', versionNumber: 2 }] }),
  },
  DatasetProfile: {
    create: jest.fn<any>().mockResolvedValue({ data: mockProfile }),
    list: jest.fn<any>().mockResolvedValue({ data: [mockProfile] }),
  },
})

// Mock the module
jest.mock('../utils/amplify-client', () => ({
  amplifyClient: createMockAmplifyClient(),
}))

// Import after mocking
const { amplifyClient } = require('../utils/amplify-client')

describe('Dataset Model Relationships', () => {
  describe('Dataset-DatasetVersion Relationships', () => {
    it('creates a dataset with initial version', async () => {
      const dataset = await amplifyClient.Dataset.create({
        name: 'Test Dataset',
        description: 'Test Description',
        scorecardId: 'test-scorecard',
        scoreId: 'test-score',
        createdAt: '2024-01-01T00:00:00.000Z',
        updatedAt: '2024-01-01T00:00:00.000Z',
      })

      const version = await amplifyClient.DatasetVersion.create({
        datasetId: dataset.data.id,
        versionNumber: 1,
        configuration: { type: 'test' },
        createdAt: '2024-01-01T00:00:00.000Z',
      })

      await amplifyClient.Dataset.update({
        id: dataset.data.id,
        currentVersionId: version.data.id,
      })

      const updatedDataset = await amplifyClient.Dataset.get({ id: dataset.data.id })
      expect(updatedDataset.data?.currentVersionId).toBe(version.data.id)
    })

    it('retrieves all versions for a dataset', async () => {
      const dataset = await amplifyClient.Dataset.create({
        name: 'Multi-Version Dataset',
        description: 'Testing version listing',
        scorecardId: 'test-scorecard',
        scoreId: 'test-score',
        createdAt: '2024-01-01T00:00:00.000Z',
        updatedAt: '2024-01-01T00:00:00.000Z',
      })

      await Promise.all([
        amplifyClient.DatasetVersion.create({
          datasetId: dataset.data.id,
          versionNumber: 1,
          configuration: { type: 'test-1' },
          createdAt: '2024-01-01T00:00:00.000Z',
        }),
        amplifyClient.DatasetVersion.create({
          datasetId: dataset.data.id,
          versionNumber: 2,
          configuration: { type: 'test-2' },
          createdAt: '2024-01-01T00:00:00.000Z',
        })
      ])

      const versions = await amplifyClient.DatasetVersion.list({
        filter: { datasetId: { eq: dataset.data.id } }
      })
      expect(versions.data.length).toBe(2)
    })
  })

  describe('Dataset-DatasetProfile Relationships', () => {
    it('creates profiles for a dataset', async () => {
      const dataset = await amplifyClient.Dataset.create({
        name: 'Profiled Dataset',
        description: 'Testing profiles',
        scorecardId: 'test-scorecard',
        scoreId: 'test-score',
        createdAt: '2024-01-01T00:00:00.000Z',
        updatedAt: '2024-01-01T00:00:00.000Z',
      })

      const version = await amplifyClient.DatasetVersion.create({
        datasetId: dataset.data.id,
        versionNumber: 1,
        configuration: { type: 'test' },
        createdAt: '2024-01-01T00:00:00.000Z',
      })

      await amplifyClient.DatasetProfile.create({
        datasetId: dataset.data.id,
        datasetVersionId: version.data.id,
        columnList: ['col1', 'col2'],
        recordCounts: { total: 100 },
        answerDistribution: { yes: 60, no: 40 },
        createdAt: '2024-01-01T00:00:00.000Z',
      })

      const profiles = await amplifyClient.DatasetProfile.list({
        filter: { datasetId: { eq: dataset.data.id } }
      })
      expect(profiles.data.length).toBe(1)
      expect(profiles.data[0].columnList).toEqual(['col1', 'col2'])
    })
  })

  describe('DatasetVersion-DatasetProfile Relationships', () => {
    it('retrieves profiles for a specific version', async () => {
      const dataset = await amplifyClient.Dataset.create({
        name: 'Version Profile Test',
        description: 'Testing version profiles',
        scorecardId: 'test-scorecard',
        scoreId: 'test-score',
        createdAt: '2024-01-01T00:00:00.000Z',
        updatedAt: '2024-01-01T00:00:00.000Z',
      })

      const version = await amplifyClient.DatasetVersion.create({
        datasetId: dataset.data.id,
        versionNumber: 1,
        configuration: { type: 'test' },
        createdAt: '2024-01-01T00:00:00.000Z',
      })

      await amplifyClient.DatasetProfile.create({
        datasetId: dataset.data.id,
        datasetVersionId: version.data.id,
        columnList: ['col1', 'col2'],
        recordCounts: { total: 100 },
        answerDistribution: { yes: 60, no: 40 },
        createdAt: '2024-01-01T00:00:00.000Z',
      })

      const versionProfiles = await amplifyClient.DatasetProfile.list({
        filter: { datasetVersionId: { eq: version.data.id } }
      })
      expect(versionProfiles.data.length).toBe(1)
      expect(versionProfiles.data[0].datasetVersionId).toBe(version.data.id)
    })
  })
}) 