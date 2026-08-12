import manifest from './action-authority.json'

export type CommandAction = keyof typeof manifest.actions
export type StorageAuthority = 'dataSources:read' | 'scoreResultAttachments:readWrite' | 'reportBlockDetails:readWrite'

type ActionEntry = {
  inherits?: string[]
  appsync: string[]
  storage: string[]
  evidence: string[]
}

const entries = manifest.actions as Record<CommandAction, ActionEntry>

function resolveAction(action: CommandAction, visiting = new Set<string>()): { appsync: string[]; storage: string[] } {
  if (visiting.has(action)) throw new Error(`command authority inheritance cycle at ${action}`)
  const entry = entries[action]
  if (!entry) throw new Error(`missing command authority entry for ${action}`)
  const next = new Set(visiting).add(action)
  const inherited = (entry.inherits || []).map((parent) => resolveAction(parent as CommandAction, next))
  return {
    appsync: [...new Set([...entry.appsync, ...inherited.flatMap((value) => value.appsync)])].sort(),
    storage: [...new Set([...entry.storage, ...inherited.flatMap((value) => value.storage)])].sort(),
  }
}

export const LIFECYCLE_APPSYNC_ROOTS = [...manifest.lifecycleAppSyncRoots]
export const REGISTERED_COMMAND_ACTIONS = Object.keys(entries).sort() as CommandAction[]
export const ACTION_AUTHORITY = Object.fromEntries(
  REGISTERED_COMMAND_ACTIONS.map((action) => [action, { ...resolveAction(action), evidence: [...entries[action].evidence] }]),
) as Record<CommandAction, { appsync: string[]; storage: StorageAuthority[]; evidence: string[] }>
export const WORKER_APPSYNC_AUTHORITY_GROUPS = [
  { id: 'Lifecycle', source: 'lifecycle', roots: [...LIFECYCLE_APPSYNC_ROOTS] },
  ...REGISTERED_COMMAND_ACTIONS.map((action) => ({
    id: action.split(/[^A-Za-z0-9]+/).filter(Boolean)
      .map((part) => `${part[0].toUpperCase()}${part.slice(1)}`).join(''),
    source: action,
    roots: [...ACTION_AUTHORITY[action].appsync],
  })),
].filter((group) => group.roots.length > 0)

export const WORKER_DOMAIN_APPSYNC_ROOTS = [...new Set(
  REGISTERED_COMMAND_ACTIONS.flatMap((action) => ACTION_AUTHORITY[action].appsync),
)].sort()

export const WORKER_STORAGE_AUTHORITIES = [...new Set(
  REGISTERED_COMMAND_ACTIONS.flatMap((action) => ACTION_AUTHORITY[action].storage),
)].sort() as StorageAuthority[]

export function appSyncFieldArn(apiGraphqlArn: string, root: string): string {
  const match = /^(Query|Mutation)\/([A-Za-z][A-Za-z0-9_]*)$/.exec(root)
  if (!match) throw new Error(`invalid AppSync root in command authority manifest: ${root}`)
  return `${apiGraphqlArn}/types/${match[1]}/fields/${match[2]}`
}
