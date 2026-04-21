import { getClient } from "@/utils/amplify-client"

const LIST_REPORT_CONFIGURATIONS = `
  query ListReportConfigurations(
    $accountId: String!
    $limit: Int
    $nextToken: String
    $sortDirection: ModelSortDirection
  ) {
    listReportConfigurationByAccountIdAndUpdatedAt(
      accountId: $accountId
      limit: $limit
      nextToken: $nextToken
      sortDirection: $sortDirection
    ) {
      items {
        id
        name
        description
        updatedAt
        createdAt
      }
      nextToken
    }
  }
`

export type ReportConfigurationListItem = {
  id: string
  name?: string | null
  description?: string | null
  updatedAt?: string | null
  createdAt?: string | null
}

export async function listAllReportConfigurationsByAccount(
  accountId: string
): Promise<ReportConfigurationListItem[]> {
  const allConfigs: ReportConfigurationListItem[] = []
  let nextToken: string | null = null

  do {
    const response = await getClient().graphql({
      query: LIST_REPORT_CONFIGURATIONS,
      variables: {
        accountId,
        limit: 100,
        nextToken,
        sortDirection: "DESC",
      },
    })

    if (
      "data" in response &&
      response.data?.listReportConfigurationByAccountIdAndUpdatedAt?.items
    ) {
      const page = response.data.listReportConfigurationByAccountIdAndUpdatedAt
      allConfigs.push(...page.items.filter(Boolean))
      nextToken = page.nextToken ?? null
    } else {
      nextToken = null
    }
  } while (nextToken)

  return allConfigs.filter(
    (config, index, arr) =>
      arr.findIndex((other) => other.id === config.id) === index
  )
}
