import manifest from "../../../services/private-graphql-proxy/schema/amplify-manifest.json"

type Manifest = typeof manifest
type ModelName = keyof Manifest["models"] & string

type GraphqlRequest = {
  query: string
  variables?: Record<string, any>
  authMode?: string
}

const endpoint = () => (
  process.env.NEXT_PUBLIC_PLEXUS_API_URL?.trim() || "http://localhost:18080/graphql"
)

const apiKey = () => (
  process.env.NEXT_PUBLIC_PLEXUS_API_KEY?.trim() || "local-smoke-key"
)

export const GraphQLResult = undefined
export const GraphQLSubscription = undefined

export function generateClient() {
  const modelCache = new Map<string, any>()
  const models = new Proxy({}, {
    get(_target, property) {
      if (typeof property !== "string") return undefined
      if (!modelCache.has(property)) {
        modelCache.set(property, createModelClient(property as ModelName))
      }
      return modelCache.get(property)
    },
  })

  return {
    models,
    graphql,
  }
}

async function graphql<T = any>({ query, variables }: GraphqlRequest): Promise<T> {
  if (/^\s*subscription\b/i.test(query)) {
    return noOpSubscription() as T
  }

  const response = await fetch(endpoint(), {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey(),
    },
    body: JSON.stringify({ query, variables: variables || {} }),
  })
  const payload = await response.json()
  if (!response.ok || payload.errors?.length) {
    const message = payload.errors?.map((error: any) => error.message).join("; ")
      || `Local GraphQL request failed with ${response.status}`
    throw Object.assign(new Error(message), payload)
  }
  return payload
}

function createModelClient(modelName: ModelName) {
  return new Proxy({
    graphql: { query: graphql },
    get: (args: Record<string, any>) => modelGet(modelName, args),
    list: (args?: Record<string, any>) => modelList(modelName, args || {}),
    create: (input: Record<string, any>) => modelMutation(modelName, "create", input),
    update: (input: Record<string, any>) => modelMutation(modelName, "update", input),
    delete: (input: Record<string, any>) => modelMutation(modelName, "delete", input),
    observeQuery: (args?: Record<string, any>) => observeQuery(modelName, args || {}),
    onCreate: () => noOpSubscription(),
    onUpdate: () => noOpSubscription(),
    onDelete: () => noOpSubscription(),
  }, {
    get(target, property) {
      if (typeof property !== "string") return undefined
      if (property in target) return (target as any)[property]
      if (property.startsWith(`list${modelName}By`)) {
        return (args?: Record<string, any>) => modelIndexList(modelName, property, args || {})
      }
      return undefined
    },
  })
}

async function modelGet(modelName: ModelName, args: Record<string, any>) {
  const root = manifest.models[modelName].operations.get
  const query = `
    query LocalGet${modelName}${operationVariables(args)} {
      ${rootCall(root, args)} {
        ${selectionSet(modelName)}
      }
    }
  `
  const response: any = await graphql({ query, variables: args })
  return { data: response.data?.[root] ?? null }
}

async function modelList(modelName: ModelName, args: Record<string, any>) {
  const root = manifest.models[modelName].operations.list
  return executeConnection(modelName, root, args, `LocalList${modelName}`)
}

async function modelIndexList(modelName: ModelName, root: string, args: Record<string, any>) {
  return executeConnection(modelName, root, args, `Local${root}`)
}

async function executeConnection(
  modelName: ModelName,
  root: string,
  args: Record<string, any>,
  operationName: string,
) {
  const query = `
    query ${operationName}${operationVariables(args)} {
      ${rootCall(root, args)} {
        items {
          ${selectionSet(modelName)}
        }
        nextToken
      }
    }
  `
  const response: any = await graphql({ query, variables: args })
  const connection = response.data?.[root] || {}
  return {
    data: connection.items || [],
    nextToken: connection.nextToken || null,
  }
}

async function modelMutation(modelName: ModelName, action: "create" | "update" | "delete", input: Record<string, any>) {
  const root = manifest.models[modelName].operations[action]
  const inputType = `${pascal(action)}${modelName}Input`
  const query = `
    mutation Local${pascal(action)}${modelName}($input: ${inputType}!) {
      ${root}(input: $input) {
        ${selectionSet(modelName)}
      }
    }
  `
  const response: any = await graphql({ query, variables: { input } })
  return { data: response.data?.[root] ?? null }
}

function observeQuery(modelName: ModelName, args: Record<string, any>) {
  return {
    subscribe(observer: any) {
      let cancelled = false
      modelList(modelName, args)
        .then((result) => {
          if (!cancelled) observer?.next?.({ items: result.data, isSynced: true })
        })
        .catch((error) => {
          if (!cancelled) observer?.error?.(error)
        })
      return {
        unsubscribe() {
          cancelled = true
        },
      }
    },
  }
}

function noOpSubscription() {
  return {
    subscribe(_observer?: any) {
      return {
        unsubscribe() {},
      }
    },
  }
}

function selectionSet(modelName: ModelName): string {
  const model = manifest.models[modelName]
  return Object.values(model.fields)
    .filter((field: any) => field.kind !== "relationship")
    .map((field: any) => field.name)
    .join("\n")
}

function variableDefinitions(args: Record<string, any>): string {
  const entries = Object.keys(args || {})
  if (entries.length === 0) return ""
  return entries.map((name) => `$${name}: AWSJSON`).join(", ")
}

function operationVariables(args: Record<string, any>): string {
  const definitions = variableDefinitions(args)
  return definitions ? `(${definitions})` : ""
}

function argumentList(args: Record<string, any>): string {
  return Object.keys(args || {}).map((name) => `${name}: $${name}`).join(", ")
}

function rootCall(root: string, args: Record<string, any>): string {
  const argsList = argumentList(args)
  return argsList ? `${root}(${argsList})` : root
}

function pascal(value: string): string {
  return value.slice(0, 1).toUpperCase() + value.slice(1)
}
