import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"

const client = generateClient<Schema>()

export type AmplifyResponse<T> = { data: T; nextToken: string | null }
export type SubscriptionResponse<T> = { items: T[] }

export const amplifyClient = {
  Account: {
    list: async (params: any) => {
      const response = await (client.models.Account as any).list(params)
      return response as AmplifyResponse<Schema['Account']['type'][]>
    },
    get: async (params: any) => {
      const response = await (client.models.Account as any).get(params)
      return { data: response.data as Schema['Account']['type'] | null }
    }
  },
  Scorecard: {
    list: async (params?: any) => {
      const response = await (client.models.Scorecard as any).list(params)
      return response as AmplifyResponse<Schema['Scorecard']['type'][]>
    },
    get: async (params: any) => {
      const response = await (client.models.Scorecard as any).get(params)
      return { data: response.data as Schema['Scorecard']['type'] | null }
    },
    create: async (data: {
      name: string
      key: string
      externalId: string
      description?: string
      accountId: string
      itemId?: string
    }) => {
      const response = await (client.models.Scorecard as any).create(data)
      return { data: response.data as Schema['Scorecard']['type'] }
    },
    update: async (data: {
      id: string
      name?: string
      key?: string
      externalId?: string
      description?: string
      itemId?: string
    }) => {
      const response = await (client.models.Scorecard as any).update(data)
      return { data: response.data as Schema['Scorecard']['type'] }
    },
    observeQuery: (params: any) => {
      return (client.models.Scorecard as any).observeQuery(params) as {
        subscribe: (handlers: {
          next: (response: SubscriptionResponse<Schema['Scorecard']['type']>) => void;
          error: (error: Error) => void;
        }) => { unsubscribe: () => void };
      }
    }
  },
  ScorecardSection: {
    list: async (params: any) => {
      const response = await (client.models.ScorecardSection as any).list(params)
      return response as AmplifyResponse<Schema['ScorecardSection']['type'][]>
    },
    create: async (data: {
      name: string
      order: number
      scorecardId: string
    }) => {
      const response = await (client.models.ScorecardSection as any).create(data)
      return { data: response.data as Schema['ScorecardSection']['type'] }
    },
    update: async (data: {
      id: string
      name?: string
      order?: number
    }) => {
      const response = await (client.models.ScorecardSection as any).update(data)
      return { data: response.data as Schema['ScorecardSection']['type'] }
    },
    delete: async (params: { id: string }) => {
      const response = await (client.models.ScorecardSection as any).delete(params)
      return { data: response.data as Schema['ScorecardSection']['type'] }
    }
  },
  Score: {
    list: async (params: any) => {
      const response = await (client.models.Score as any).list(params)
      return response as AmplifyResponse<Schema['Score']['type'][]>
    },
    create: async (data: {
      name: string
      type: string
      order: number
      sectionId: string
      accuracy?: number
      version?: string
      aiProvider?: string
      aiModel?: string
      isFineTuned?: boolean
      configuration?: any
      distribution?: any[]
      versionHistory?: any[]
    }) => {
      const response = await (client.models.Score as any).create(data)
      return { data: response.data as Schema['Score']['type'] }
    },
    update: async (data: {
      id: string
      name?: string
      type?: string
      order?: number
      sectionId?: string
      accuracy?: number
      version?: string
      aiProvider?: string
      aiModel?: string
      isFineTuned?: boolean
      configuration?: any
      distribution?: any[]
      versionHistory?: any[]
    }) => {
      const response = await (client.models.Score as any).update(data)
      return { data: response.data as Schema['Score']['type'] }
    },
    delete: async (params: { id: string }) => {
      const response = await (client.models.Score as any).delete(params)
      return { data: response.data as Schema['Score']['type'] }
    }
  }
} 