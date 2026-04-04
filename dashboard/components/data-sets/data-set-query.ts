import type { Schema } from '@/amplify/data/resource'
import { graphqlRequest, handleGraphQLErrors } from '@/utils/amplify-client'

export type DataSetBrowseMode = 'associated' | 'sourceScoped'
export type AssociatedDataSetFilterType =
  | 'all'
  | 'scorecard'
  | 'score'
  | 'scoreVersion'
  | 'dataSourceVersion'

export interface DataSetBrowseOptions {
  accountId: string
  mode: DataSetBrowseMode
  dataSourceVersionId?: string | null
  associatedFilter?: AssociatedDataSetFilterType
  associatedFilterValue?: string | null
}

const byNewestFirst = (
  a: Schema['DataSet']['type'],
  b: Schema['DataSet']['type']
): number => {
  const createdDelta = new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  if (createdDelta !== 0) return createdDelta
  return b.id.localeCompare(a.id)
}

interface DataSetQueryConfig {
  query: string
  rootField:
    | 'listDataSetByAccountIdAndCreatedAt'
    | 'listDataSetByScorecardIdAndCreatedAt'
    | 'listDataSetByScoreIdAndCreatedAt'
    | 'listDataSetByScoreVersionIdAndCreatedAt'
    | 'listDataSetByDataSourceVersionIdAndCreatedAt'
  variableName: 'accountId' | 'scorecardId' | 'scoreId' | 'scoreVersionId' | 'dataSourceVersionId'
}

function resolveQueryConfig(filterType: AssociatedDataSetFilterType): DataSetQueryConfig {
  if (filterType === 'all') {
    return {
      query: `
        query ListDataSetByAccountIdAndCreatedAt(
          $accountId: String!
          $sortDirection: ModelSortDirection
          $limit: Int
          $nextToken: String
        ) {
          listDataSetByAccountIdAndCreatedAt(
            accountId: $accountId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
          ) {
            items {
              id
              name
              description
              file
              attachedFiles
              accountId
              scorecardId
              scoreId
              scoreVersionId
              dataSourceVersionId
              createdAt
              updatedAt
            }
            nextToken
          }
        }
      `,
      rootField: 'listDataSetByAccountIdAndCreatedAt',
      variableName: 'accountId',
    }
  }

  if (filterType === 'scorecard') {
    return {
      query: `
        query ListDataSetByScorecardIdAndCreatedAt(
          $scorecardId: String!
          $sortDirection: ModelSortDirection
          $limit: Int
          $nextToken: String
        ) {
          listDataSetByScorecardIdAndCreatedAt(
            scorecardId: $scorecardId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
          ) {
            items {
              id
              name
              description
              file
              attachedFiles
              accountId
              scorecardId
              scoreId
              scoreVersionId
              dataSourceVersionId
              createdAt
              updatedAt
            }
            nextToken
          }
        }
      `,
      rootField: 'listDataSetByScorecardIdAndCreatedAt',
      variableName: 'scorecardId',
    }
  }

  if (filterType === 'score') {
    return {
      query: `
        query ListDataSetByScoreIdAndCreatedAt(
          $scoreId: String!
          $sortDirection: ModelSortDirection
          $limit: Int
          $nextToken: String
        ) {
          listDataSetByScoreIdAndCreatedAt(
            scoreId: $scoreId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
          ) {
            items {
              id
              name
              description
              file
              attachedFiles
              accountId
              scorecardId
              scoreId
              scoreVersionId
              dataSourceVersionId
              createdAt
              updatedAt
            }
            nextToken
          }
        }
      `,
      rootField: 'listDataSetByScoreIdAndCreatedAt',
      variableName: 'scoreId',
    }
  }

  if (filterType === 'scoreVersion') {
    return {
      query: `
        query ListDataSetByScoreVersionIdAndCreatedAt(
          $scoreVersionId: String!
          $sortDirection: ModelSortDirection
          $limit: Int
          $nextToken: String
        ) {
          listDataSetByScoreVersionIdAndCreatedAt(
            scoreVersionId: $scoreVersionId
            sortDirection: $sortDirection
            limit: $limit
            nextToken: $nextToken
          ) {
            items {
              id
              name
              description
              file
              attachedFiles
              accountId
              scorecardId
              scoreId
              scoreVersionId
              dataSourceVersionId
              createdAt
              updatedAt
            }
            nextToken
          }
        }
      `,
      rootField: 'listDataSetByScoreVersionIdAndCreatedAt',
      variableName: 'scoreVersionId',
    }
  }

  return {
    query: `
      query ListDataSetByDataSourceVersionIdAndCreatedAt(
        $dataSourceVersionId: String!
        $sortDirection: ModelSortDirection
        $limit: Int
        $nextToken: String
      ) {
        listDataSetByDataSourceVersionIdAndCreatedAt(
          dataSourceVersionId: $dataSourceVersionId
          sortDirection: $sortDirection
          limit: $limit
          nextToken: $nextToken
        ) {
          items {
            id
            name
            description
            file
            attachedFiles
            accountId
            scorecardId
            scoreId
            scoreVersionId
            dataSourceVersionId
            createdAt
            updatedAt
          }
          nextToken
        }
      }
    `,
    rootField: 'listDataSetByDataSourceVersionIdAndCreatedAt',
    variableName: 'dataSourceVersionId',
  }
}

export async function listDataSetsForBrowse(
  options: DataSetBrowseOptions
): Promise<Schema['DataSet']['type'][]> {
  const {
    accountId,
    mode,
    dataSourceVersionId,
    associatedFilter,
    associatedFilterValue,
  } = options

  if (!accountId) return []

  const filterType: AssociatedDataSetFilterType =
    mode === 'sourceScoped' ? 'dataSourceVersion' : associatedFilter || 'all'
  const filterValue =
    filterType === 'all'
      ? accountId
      : (mode === 'sourceScoped' ? dataSourceVersionId : associatedFilterValue)?.trim() || ''

  if (!filterValue) {
    return []
  }

  const config = resolveQueryConfig(filterType)

  const datasets: Schema['DataSet']['type'][] = []
  let nextToken: string | null | undefined = null

  do {
    const variables: Record<string, unknown> = {
      [config.variableName]: filterValue,
      sortDirection: 'DESC',
      limit: 200,
      nextToken: nextToken ?? undefined,
    }
    const response = await graphqlRequest<any>(config.query, variables)
    handleGraphQLErrors(response)

    const result = response.data?.[config.rootField]
    const items: Schema['DataSet']['type'][] = result?.items ?? []
    datasets.push(...items)
    nextToken = result?.nextToken
  } while (nextToken)

  const accountScoped = datasets.filter((dataset) => dataset.accountId === accountId)
  return accountScoped.sort(byNewestFirst)
}
