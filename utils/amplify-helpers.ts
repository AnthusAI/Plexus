import type { Schema } from "@/amplify/data/resource"
import type { AmplifyListResult, AmplifyGetResult } from "@/types/shared"

export async function listFromModel<T>(
  model: any,
  filter?: Record<string, any>
): Promise<AmplifyListResult<T>> {
  const response = await model.list(filter ? { filter } : undefined)
  return response as AmplifyListResult<T>
}

export function observeQueryFromModel<T>(
  model: any,
  filter?: Record<string, any>
) {
  return (model.observeQuery({
    filter: filter ? filter : undefined
  }) as any) as { subscribe: (handlers: { 
    next: (data: { items: T[] }) => void
    error: (error: Error) => void 
  }) => { unsubscribe: () => void } }
}

export async function getFromModel<T>(
  model: any,
  id: string
): Promise<AmplifyGetResult<T>> {
  const response = await model.get({ id })
  return response as AmplifyGetResult<T>
} 