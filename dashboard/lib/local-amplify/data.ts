import manifest from "../../../services/private-graphql-proxy/schema/amplify-manifest.json"

type Manifest = typeof manifest
type ModelName = keyof Manifest["models"] & string

type GraphqlRequest = {
  query: string
  variables?: Record<string, any>
  authMode?: string
}

type SubscriptionAction = "create" | "update" | "delete"
type SubscriptionObserver = { next?: (value: any) => void; error?: (error: unknown) => void }
type SubscriptionDefinition = { action: SubscriptionAction; modelName: ModelName; root: string }

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

function graphql<T = any>({ query, variables }: GraphqlRequest): Promise<T> | T {
  if (/^\s*subscription\b/i.test(query)) {
    return createPollingSubscription(parseSubscription(query), variables || {}) as T
  }

  return executeGraphqlFetch<T>(query, variables)
}

async function executeGraphqlFetch<T = any>(
  query: string,
  variables?: Record<string, any>,
): Promise<T> {
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
    onCreate: (args?: Record<string, any>) => createPollingSubscription(modelSubscription(modelName, "create"), args || {}, true),
    onUpdate: (args?: Record<string, any>) => createPollingSubscription(modelSubscription(modelName, "update"), args || {}, true),
    onDelete: (args?: Record<string, any>) => createPollingSubscription(modelSubscription(modelName, "delete"), args || {}, true),
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

function createPollingSubscription(definition: SubscriptionDefinition, args: Record<string, any>, modelShape = false) {
  return {
    subscribe(observer?: SubscriptionObserver) {
      let stopped = false
      let timer: ReturnType<typeof setTimeout> | undefined
      let previous: Map<string, string> | undefined
      const interval = pollingIntervalMilliseconds()

      const poll = async () => {
        try {
          const result = await modelList(definition.modelName, subscriptionListArgs(args))
          if (stopped) return
          const items = result.data as Record<string, any>[]
          const current = new Map(items.map((item) => [stableItemId(item), snapshot(item)]))
          if (previous) {
            for (const item of changes(definition.action, previous, current, items)) {
              observer?.next?.(modelShape ? { data: item } : { data: { [definition.root]: item } })
            }
          }
          previous = current
          timer = setTimeout(poll, interval)
        } catch (error) {
          if (!stopped) { stopped = true; observer?.error?.(error) }
        }
      }
      void poll()
      return {
        unsubscribe() { stopped = true; if (timer) clearTimeout(timer) },
      }
    },
  }
}

function parseSubscription(query: string): SubscriptionDefinition {
  const match = query.match(/\b(on(Create|Update|Delete)([A-Za-z][A-Za-z0-9_]*))\s*(?:\([^)]*\))?\s*\{/)
  if (!match) throw new Error("Local GraphQL subscriptions require one supported onCreate/onUpdate/onDelete root field")
  const [, root, actionName, modelName] = match
  if (!(modelName in manifest.models)) throw new Error(`Local GraphQL subscription ${root} targets unknown model ${modelName}`)
  const definition = modelSubscription(modelName as ModelName, actionName.toLowerCase() as SubscriptionAction)
  if (definition.root !== root) throw new Error(`Local GraphQL subscription ${root} is not declared in the schema manifest`)
  return definition
}

function modelSubscription(modelName: ModelName, action: SubscriptionAction): SubscriptionDefinition {
  const root = `on${pascal(action)}${modelName}`
  const supported = manifest.models[modelName].operations.subscriptions as readonly string[]
  if (!supported.includes(root)) throw new Error(`Local GraphQL subscription ${root} is not declared in the schema manifest`)
  return { action, modelName, root }
}

function pollingIntervalMilliseconds(): number {
  const configured = process.env.NEXT_PUBLIC_PLEXUS_LOCAL_SUBSCRIPTION_POLL_MS?.trim()
  if (!configured) return 1000
  const interval = Number(configured)
  if (!Number.isFinite(interval) || interval <= 0) throw new Error("NEXT_PUBLIC_PLEXUS_LOCAL_SUBSCRIPTION_POLL_MS must be a positive number")
  return interval
}

function subscriptionListArgs(args: Record<string, any>): Record<string, any> {
  return args.filter === undefined ? {} : { filter: args.filter }
}

function stableItemId(item: Record<string, any>): string {
  if (typeof item.id !== "string" || !item.id) throw new Error("Local subscription polling requires model items with a stable id")
  return item.id
}

function changes(action: SubscriptionAction, previous: Map<string, string>, current: Map<string, string>, currentItems: Record<string, any>[]): Record<string, any>[] {
  if (action === "delete") return Array.from(previous.entries()).filter(([id]) => !current.has(id)).map(([id, itemSnapshot]) => ({ ...JSON.parse(itemSnapshot), id }))
  return currentItems.filter((item) => {
    const id = stableItemId(item)
    return action === "create" ? !previous.has(id) : previous.has(id) && previous.get(id) !== current.get(id)
  })
}

function snapshot(value: any): string { return JSON.stringify(sortJson(value)) }
function sortJson(value: any): any {
  if (Array.isArray(value)) return value.map(sortJson)
  if (!value || typeof value !== "object") return value
  return Object.keys(value).sort().reduce((result, key) => { result[key] = sortJson(value[key]); return result }, {} as Record<string, any>)
}

function selectionSet(modelName: ModelName): string {
  const model = manifest.models[modelName]
  const scalarFieldNames = Object.values(model.fields)
    .filter((field: any) => field.kind !== "relationship")
    .map((field: any) => field.name)
  const selectedFields = new Set<string>([
    ...(model.primaryKey || []),
    ...scalarFieldNames,
  ])
  return Array.from(selectedFields).join("\n")
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
