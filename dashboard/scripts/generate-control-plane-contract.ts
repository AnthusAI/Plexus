import { createHash } from "node:crypto"
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { basename, dirname, join, relative, resolve } from "node:path"
import { fileURLToPath } from "node:url"

const GENERATOR_VERSION = "1.1.0"

const scriptDir = dirname(fileURLToPath(import.meta.url))
const dashboardDir = resolve(scriptDir, "..")
const repoRoot = resolve(dashboardDir, "..")
const defaultOutDir = join(repoRoot, "services/private-graphql-proxy/schema")

const dataResourcePath = join(dashboardDir, "amplify/data/resource.ts")
const authResourcePath = join(dashboardDir, "amplify/auth/resource.ts")
const storageResourcePath = join(dashboardDir, "amplify/storage/resource.ts")
const packageJsonPath = join(dashboardDir, "package.json")
const packageLockPath = join(dashboardDir, "package-lock.json")

type Manifest = {
  contractVersion: string
  generator: Record<string, unknown>
  sources: Record<string, { sha256: string }>
  models: Record<string, ModelManifest>
  indexes: Record<string, IndexManifest[]>
  relationships: RelationshipManifest[]
  customTypes: Record<string, CustomTypeManifest>
  customOperations: Record<string, CustomOperationManifest>
  authRules: Record<string, string[]>
  subscriptions: Record<string, SubscriptionManifest>
  storage: Record<string, StorageManifest>
}

type ModelManifest = {
  name: string
  fields: Record<string, FieldManifest>
  primaryKey: string[]
  authRules: string[]
  operations: {
    get: string
    list: string
    create: string
    update: string
    delete: string
    indexes: string[]
    subscriptions: string[]
  }
}

type FieldManifest = {
  name: string
  kind: "scalar" | "enum" | "relationship" | "ref" | "unknown"
  type: string
  isRequired: boolean
  isArray: boolean
  enumValues?: string[]
  relationship?: {
    kind: "hasOne" | "hasMany" | "belongsTo"
    targetModel: string
    targetField: string
  }
}

type IndexManifest = {
  name: string
  queryField: string
  partitionField: string
  sortFields: string[]
  sortArgument?: string
  arguments: string[]
  compositeBeginsWith?: Record<string, string>
}

type RelationshipManifest = {
  model: string
  field: string
  kind: string
  targetModel: string
  targetField: string
  connectionShape: "object" | "connection"
}

type CustomTypeManifest = {
  name: string
  fields: Record<string, FieldManifest>
}

type CustomOperationManifest = {
  name: string
  operationType: "query" | "mutation" | "subscription"
  arguments: Record<string, FieldManifest>
  returnType?: string
  returnIsArray?: boolean
  returnIsRequired?: boolean
  authRules: string[]
  handler?: string
}

type SubscriptionManifest = {
  model: string
  onCreate: string
  onUpdate: string
  onDelete: string
}

type StorageManifest = {
  exportName: string
  name: string
  isDefault: boolean
  access: Record<string, Array<{ principal: string; operations: string[] }>>
}

function main() {
  const args = parseArgs(process.argv.slice(2))
  const outDir = args.outDir || defaultOutDir

  if (args.check) {
    const tempDir = mkdtempSync(join(tmpdir(), "plexus-schema-contract-"))
    try {
      generate(tempDir)
      const diffs = compareGenerated(tempDir, outDir)
      if (diffs.length > 0) {
        console.error("Schema contract artifacts are out of date:")
        for (const diff of diffs) {
          console.error(`- ${diff}`)
        }
        process.exitCode = 1
      }
    } finally {
      rmSync(tempDir, { recursive: true, force: true })
    }
    return
  }

  generate(outDir)
}

function parseArgs(args: string[]) {
  const parsed: { outDir?: string; check?: boolean } = {}
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index]
    if (arg === "--check") {
      parsed.check = true
    } else if (arg === "--out") {
      parsed.outDir = resolve(args[index + 1])
      index += 1
    }
  }
  return parsed
}

function generate(outDir: string) {
  mkdirSync(outDir, { recursive: true })
  const manifest = buildManifest()
  const sdl = buildGraphqlSchema(manifest)
  const manifestSchema = buildManifestJsonSchema()
  const version = buildSchemaVersion(manifest, sdl)

  writeJson(join(outDir, "amplify-manifest.json"), manifest)
  writeFileSync(join(outDir, "amplify.graphql"), `${sdl.trim()}\n`)
  writeJson(join(outDir, "amplify-manifest.schema.json"), manifestSchema)
  writeJson(join(outDir, "schema-version.json"), version)
}

function buildManifest(): Manifest {
  const dataSource = readFileSync(dataResourcePath, "utf8")
  const authSource = readFileSync(authResourcePath, "utf8")
  const storageSource = readFileSync(storageResourcePath, "utf8")
  const parsedDataSource = stripComments(dataSource)
  const schemaBody = objectBody(findCall(parsedDataSource, "a.schema"))
  const schemaEntries = parseObjectEntries(schemaBody)

  const models: Record<string, ModelManifest> = {}
  const indexes: Record<string, IndexManifest[]> = {}
  const relationships: RelationshipManifest[] = []
  const customTypes: Record<string, CustomTypeManifest> = {}
  const customOperations: Record<string, CustomOperationManifest> = {}
  const authRules: Record<string, string[]> = {}
  const subscriptions: Record<string, SubscriptionManifest> = {}

  for (const [name, expression] of schemaEntries) {
    if (expression.includes(".model(")) {
      const model = parseModel(name, expression)
      models[name] = model
      indexes[name] = parseIndexes(name, expression)
      authRules[name] = model.authRules
      subscriptions[name] = {
        model: name,
        onCreate: `onCreate${name}`,
        onUpdate: `onUpdate${name}`,
        onDelete: `onDelete${name}`,
      }
      model.operations.indexes = indexes[name].map((index) => index.queryField)
      model.operations.subscriptions = [
        subscriptions[name].onCreate,
        subscriptions[name].onUpdate,
        subscriptions[name].onDelete,
      ]
      for (const field of Object.values(model.fields)) {
        if (field.relationship) {
          relationships.push({
            model: name,
            field: field.name,
            kind: field.relationship.kind,
            targetModel: field.relationship.targetModel,
            targetField: field.relationship.targetField,
            connectionShape: field.relationship.kind === "hasMany" ? "connection" : "object",
          })
        }
      }
    } else if (expression.includes("a.customType(")) {
      customTypes[name] = parseCustomType(name, expression)
    } else if (expression.includes(".query(") || expression.includes(".mutation(")) {
      const operation = parseCustomOperation(
        name,
        expression.includes(".mutation(") ? "mutation" : "query",
        expression,
      )
      customOperations[name] = operation
      authRules[name] = operation.authRules
    }
  }

  return {
    contractVersion: contractVersionFor(dataSource, authSource, storageSource),
    generator: {
      version: GENERATOR_VERSION,
      strategy: "amplify-runtime-first-with-static-dsl-fallback",
      runtimeProbe: probeAmplifyRuntime(),
      packageVersions: packageVersions(),
    },
    sources: {
      [relative(repoRoot, dataResourcePath)]: { sha256: sha256(dataSource) },
      [relative(repoRoot, authResourcePath)]: { sha256: sha256(authSource) },
      [relative(repoRoot, storageResourcePath)]: { sha256: sha256(storageSource) },
    },
    models,
    indexes,
    relationships,
    customTypes,
    customOperations,
    authRules,
    subscriptions,
    storage: parseStorage(stripComments(storageSource)),
  }
}

function parseModel(name: string, expression: string): ModelManifest {
  const modelBody = objectBody(findCall(expression, ".model"))
  const fieldEntries = parseObjectEntries(modelBody)
  const fields: Record<string, FieldManifest> = {}

  for (const [fieldName, fieldExpression] of fieldEntries) {
    fields[fieldName] = parseField(fieldName, fieldExpression)
  }

  return {
    name,
    fields,
    primaryKey: parseIdentifier(expression) || ["id"],
    authRules: parseAuthRules(expression),
    operations: {
      get: `get${name}`,
      list: `list${pluralize(name)}`,
      create: `create${name}`,
      update: `update${name}`,
      delete: `delete${name}`,
      indexes: [],
      subscriptions: [],
    },
  }
}

function parseCustomType(name: string, expression: string): CustomTypeManifest {
  const body = objectBody(findCall(expression, "a.customType"))
  const fields: Record<string, FieldManifest> = {}
  for (const [fieldName, fieldExpression] of parseObjectEntries(body)) {
    fields[fieldName] = parseField(fieldName, fieldExpression)
  }
  return { name, fields }
}

function parseCustomOperation(
  name: string,
  operationType: "query" | "mutation" | "subscription",
  expression: string,
): CustomOperationManifest {
  const argsMatch = expression.match(/\.arguments\(\s*(\{[\s\S]*?\})\s*\)/)
  const args = argsMatch ? parseObjectEntries(objectBody(argsMatch[1])) : []
  const operationArgs: Record<string, FieldManifest> = {}
  for (const [argName, argExpression] of args) {
    operationArgs[argName] = parseField(argName, argExpression)
  }
  const returnsExpression = findOptionalCall(expression, ".returns")
  const returnsMatch = returnsExpression?.match(/a\.ref\(['"]([^'"]+)['"]\)/)
  const handlerMatch = expression.match(/\.handler\(\s*a\.handler\.function\(([^)]+)\)\s*\)/)
  return {
    name,
    operationType,
    arguments: operationArgs,
    returnType: returnsMatch?.[1],
    returnIsArray: returnsExpression?.includes(".array()"),
    returnIsRequired: returnsExpression?.includes(".required()"),
    authRules: parseAuthRules(expression),
    handler: handlerMatch?.[1]?.trim(),
  }
}

function parseField(name: string, expression: string): FieldManifest {
  const relationship = expression.match(/a\.(hasOne|hasMany|belongsTo)\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*\)/)
  if (relationship) {
    return {
      name,
      kind: "relationship",
      type: relationship[2],
      isRequired: expression.includes(".required()"),
      isArray: relationship[1] === "hasMany",
      relationship: {
        kind: relationship[1] as "hasOne" | "hasMany" | "belongsTo",
        targetModel: relationship[2],
        targetField: relationship[3],
      },
    }
  }

  const enumMatch = expression.match(/a\.enum\(\s*\[([\s\S]*?)\]\s*\)/)
  if (enumMatch) {
    return {
      name,
      kind: "enum",
      type: `${pascalCase(name)}Enum`,
      isRequired: expression.includes(".required()"),
      isArray: expression.includes(".array()"),
      enumValues: stringArrayValues(enumMatch[1]),
    }
  }

  const refMatch = expression.match(/a\.ref\(['"]([^'"]+)['"]\)/)
  if (refMatch) {
    return {
      name,
      kind: "ref",
      type: refMatch[1],
      isRequired: expression.includes(".required()"),
      isArray: expression.includes(".array()"),
    }
  }

  const scalarMatch = expression.match(/a\.(string|integer|float|boolean|datetime|id|json)\(/)
  return {
    name,
    kind: scalarMatch ? "scalar" : "unknown",
    type: scalarMatch ? scalarMatch[1] : "unknown",
    isRequired: expression.includes(".required()"),
    isArray: expression.includes(".array()"),
  }
}

function parseIdentifier(expression: string): string[] | null {
  const match = expression.match(/\.identifier\(\s*\[([\s\S]*?)\]\s*\)/)
  if (!match) {
    return null
  }
  return stringArrayValues(match[1])
}

function parseIndexes(modelName: string, expression: string): IndexManifest[] {
  const call = findOptionalCall(expression, ".secondaryIndexes")
  if (!call) {
    return []
  }
  const array = firstBalanced(call, "[", "]")
  if (!array) {
    return []
  }
  const indexes: IndexManifest[] = []
  const itemRegex = /(?:idx|index)\(\s*["']([^"']+)["']\s*\)(?:\s*\.sortKeys\(\s*\[([\s\S]*?)\]\s*\))?(?:\s*\.name\(\s*["']([^"']+)["']\s*\))?/g
  let match: RegExpExecArray | null
  while ((match = itemRegex.exec(array)) !== null) {
    const partitionField = match[1]
    const sortFields = match[2] ? stringArrayValues(match[2]) : []
    const defaultQuerySuffix = [
      pascalCase(partitionField),
      ...sortFields.map((field) => `And${pascalCase(field)}`),
    ].join("")
    const indexName = match[3] || `by${defaultQuerySuffix}`
    const querySuffix = indexName.startsWith("by") ? indexName.slice(2) : indexName
    const sortArgument = sortFields.length === 0 ? undefined : sortFields.map((field, index) => (
      index === 0 ? field : pascalCase(field)
    )).join("")
    indexes.push({
      name: indexName,
      queryField: `list${modelName}By${querySuffix}`,
      partitionField,
      sortFields,
      sortArgument,
      arguments: [partitionField, ...(sortArgument ? [sortArgument] : []), "filter", "sortDirection", "limit", "nextToken"],
      compositeBeginsWith: sortFields.length > 1
        ? Object.fromEntries(sortFields.map((field) => [field, scalarTypeName(field)]))
        : undefined,
    })
  }
  return indexes
}

function parseAuthRules(expression: string): string[] {
  const call = findOptionalCall(expression, ".authorization")
  if (!call) {
    return []
  }
  const rules = new Set<string>()
  if (call.includes("allow.guest()")) {
    rules.add("guest")
  }
  if (call.includes("allow.publicApiKey()")) {
    rules.add("apiKey")
  }
  if (call.includes("allow.authenticated()")) {
    rules.add("authenticated")
  }
  if (call.includes("allow.authenticated('identityPool')") || call.includes('allow.authenticated("identityPool")')) {
    rules.add("iam")
  }
  return [...rules]
}

function parseStorage(source: string): Record<string, StorageManifest> {
  const storage: Record<string, StorageManifest> = {}
  const exportRegex = /export\s+const\s+(\w+)\s*=\s*defineStorage\(/g
  let match: RegExpExecArray | null
  while ((match = exportRegex.exec(source)) !== null) {
    const exportName = match[1]
    const call = balancedFrom(source, source.indexOf("(", match.index))
    const body = objectBody(call)
    const name = body.match(/name:\s*['"]([^'"]+)['"]/)?.[1] || exportName
    const isDefault = /isDefault:\s*true/.test(body)
    const access: StorageManifest["access"] = {}
    const accessStart = body.indexOf("access:")
    const accessExpression = accessStart >= 0 ? body.slice(accessStart) : body
    const objectStart = accessExpression.indexOf("{")
    const accessBody = objectStart >= 0
      ? balancedFrom(accessExpression, objectStart).slice(1, -1)
      : ""

    for (const [prefix, grantsExpression] of parseObjectEntries(accessBody)) {
      const entries: Array<{ principal: string; operations: string[] }> = []
      const grantRegex = /allow\.(guest|authenticated)\.to\(\s*\[([\s\S]*?)\]\s*\)/g
      let grantMatch: RegExpExecArray | null
      while ((grantMatch = grantRegex.exec(grantsExpression)) !== null) {
        entries.push({
          principal: grantMatch[1],
          operations: stringArrayValues(grantMatch[2]),
        })
      }
      access[prefix] = entries
    }
    storage[exportName] = { exportName, name, isDefault, access }
  }
  return storage
}

function buildGraphqlSchema(manifest: Manifest): string {
  const enumBlocks: string[] = []
  const typeBlocks: string[] = []
  const inputBlocks: string[] = []
  const queryFields: string[] = []
  const mutationFields: string[] = []
  const subscriptionFields: string[] = []

  for (const model of Object.values(manifest.models)) {
    for (const field of Object.values(model.fields)) {
      if (field.kind === "enum" && field.enumValues?.length) {
        enumBlocks.push(`enum ${model.name}${pascalCase(field.name)}Enum {\n${field.enumValues.map((value) => `  ${value}`).join("\n")}\n}`)
      }
    }
  }

  for (const customType of Object.values(manifest.customTypes)) {
    for (const field of Object.values(customType.fields)) {
      if (field.kind === "enum" && field.enumValues?.length) {
        enumBlocks.push(`enum ${pascalCase(field.name)}Enum {\n${field.enumValues.map((value) => `  ${value}`).join("\n")}\n}`)
      }
    }
  }

  for (const customType of Object.values(manifest.customTypes)) {
    typeBlocks.push(`type ${customType.name} {\n${Object.values(customType.fields).map((field) => `  ${field.name}: ${graphqlFieldType(field)}`).join("\n")}\n}`)
  }

  const customInputTypes = new Set<string>()
  for (const operation of Object.values(manifest.customOperations)) {
    for (const argument of Object.values(operation.arguments)) {
      if (argument.kind === "ref" && manifest.customTypes[argument.type]) {
        customInputTypes.add(argument.type)
      }
    }
  }
  for (const customTypeName of customInputTypes) {
    const customType = manifest.customTypes[customTypeName]
    inputBlocks.push(`input ${customType.name}Input {\n${Object.values(customType.fields).map((field) => `  ${field.name}: ${graphqlInputType(field)}`).join("\n")}\n}`)
  }

  for (const model of Object.values(manifest.models)) {
    typeBlocks.push(`type ${model.name} {\n${Object.values(model.fields).map((field) => `  ${field.name}: ${graphqlFieldType(field, model.name)}`).join("\n")}\n}`)
    typeBlocks.push(`type Model${model.name}Connection {\n  items: [${model.name}]\n  nextToken: String\n}`)
    inputBlocks.push(`input Create${model.name}Input {\n${Object.values(model.fields).filter(isInputField).map((field) => `  ${field.name}: ${graphqlInputType(field)}`).join("\n")}\n}`)
    inputBlocks.push(`input Update${model.name}Input {\n${Object.values(model.fields).filter(isInputField).map((field) => `  ${field.name}: ${graphqlInputType({ ...field, isRequired: false })}`).join("\n")}\n}`)
    inputBlocks.push(`input Delete${model.name}Input {\n${model.primaryKey.map((field) => `  ${field}: ID!`).join("\n")}\n}`)
    queryFields.push(`  ${model.operations.get}(${model.primaryKey.map((field) => `${field}: ID!`).join(", ")}): ${model.name}`)
    queryFields.push(`  ${model.operations.list}(filter: Model${model.name}FilterInput, sortDirection: ModelSortDirection, limit: Int, nextToken: String): Model${model.name}Connection`)
    inputBlocks.push(`input Model${model.name}FilterInput {\n${Object.values(model.fields).filter(isInputField).map((field) => `  ${field.name}: ModelStringInput`).join("\n")}\n}`)
    for (const index of manifest.indexes[model.name] || []) {
      queryFields.push(`  ${index.queryField}(${index.arguments.map((arg) => `${arg}: ${arg === index.partitionField ? "String!" : indexArgumentType(arg, index)}`).join(", ")}): Model${model.name}Connection`)
    }
    mutationFields.push(`  ${model.operations.create}(input: Create${model.name}Input!): ${model.name}`)
    mutationFields.push(`  ${model.operations.update}(input: Update${model.name}Input!): ${model.name}`)
    mutationFields.push(`  ${model.operations.delete}(input: Delete${model.name}Input!): ${model.name}`)
    subscriptionFields.push(`  ${manifest.subscriptions[model.name].onCreate}: ${model.name}`)
    subscriptionFields.push(`  ${manifest.subscriptions[model.name].onUpdate}: ${model.name}`)
    subscriptionFields.push(`  ${manifest.subscriptions[model.name].onDelete}: ${model.name}`)
  }

  for (const operation of Object.values(manifest.customOperations)) {
    const args = Object.values(operation.arguments).map((field) => `${field.name}: ${graphqlCustomOperationInputType(field, manifest.customTypes)}`).join(", ")
    const returnType = graphqlCustomOperationReturnType(operation)
    if (operation.operationType === "query") {
      queryFields.push(`  ${operation.name}(${args}): ${returnType}`)
    } else if (operation.operationType === "mutation") {
      mutationFields.push(`  ${operation.name}(${args}): ${returnType}`)
    }
  }

  return [
    "scalar AWSDateTime",
    "scalar AWSJSON",
    "enum ModelSortDirection {\n  ASC\n  DESC\n}",
    "input ModelStringInput {\n  eq: String\n  beginsWith: String\n  contains: String\n}",
    "input ModelStringKeyConditionInput {\n  eq: String\n  le: String\n  lt: String\n  ge: String\n  gt: String\n  between: [String]\n  beginsWith: String\n}",
    ...enumBlocks,
    ...typeBlocks,
    ...inputBlocks,
    `type Query {\n${queryFields.join("\n")}\n}`,
    `type Mutation {\n${mutationFields.join("\n")}\n}`,
    `type Subscription {\n${subscriptionFields.join("\n")}\n}`,
    "schema {\n  query: Query\n  mutation: Mutation\n  subscription: Subscription\n}",
  ].join("\n\n")
}

function graphqlFieldType(field: FieldManifest, modelName?: string): string {
  if (field.kind === "relationship" && field.relationship?.kind === "hasMany") {
    return `Model${field.relationship.targetModel}Connection`
  }
  const type = field.kind === "enum" && modelName ? `${modelName}${pascalCase(field.name)}Enum` : graphqlScalar(field.type)
  const wrapped = field.isArray ? `[${type}]` : type
  return field.isRequired ? `${wrapped}!` : wrapped
}

function graphqlInputType(field: FieldManifest): string {
  const type = graphqlScalar(field.type)
  const wrapped = field.isArray ? `[${type}]` : type
  return field.isRequired ? `${wrapped}!` : wrapped
}

function graphqlCustomOperationInputType(
  field: FieldManifest,
  customTypes: Manifest["customTypes"],
): string {
  const type = field.kind === "ref" && customTypes[field.type]
    ? `${field.type}Input`
    : graphqlScalar(field.type)
  const wrapped = field.isArray ? `[${type}!]` : type
  return field.isRequired ? `${wrapped}!` : wrapped
}

function graphqlCustomOperationReturnType(operation: CustomOperationManifest): string {
  const type = operation.returnType || "AWSJSON"
  const wrapped = operation.returnIsArray ? `[${type}!]` : type
  return operation.returnIsRequired ? `${wrapped}!` : wrapped
}

function indexArgumentType(arg: string, index: IndexManifest): string {
  if (arg === "filter") {
    return "AWSJSON"
  }
  if (arg === "sortDirection") {
    return "ModelSortDirection"
  }
  if (arg === "limit") {
    return "Int"
  }
  if (arg === "nextToken") {
    return "String"
  }
  return index.sortFields.length > 1 ? "AWSJSON" : "ModelStringKeyConditionInput"
}

function isInputField(field: FieldManifest): boolean {
  return field.kind !== "relationship"
}

function graphqlScalar(type: string): string {
  switch (type) {
    case "integer":
      return "Int"
    case "float":
      return "Float"
    case "boolean":
      return "Boolean"
    case "datetime":
      return "AWSDateTime"
    case "id":
      return "ID"
    case "json":
      return "AWSJSON"
    default:
      return type === "unknown" ? "AWSJSON" : type[0]?.toUpperCase() + type.slice(1)
  }
}

function buildManifestJsonSchema() {
  return {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    type: "object",
    required: [
      "contractVersion",
      "generator",
      "sources",
      "models",
      "indexes",
      "relationships",
      "customTypes",
      "customOperations",
      "authRules",
      "subscriptions",
      "storage",
    ],
    properties: {
      contractVersion: { type: "string" },
      generator: { type: "object" },
      sources: { type: "object" },
      models: { type: "object" },
      indexes: { type: "object" },
      relationships: { type: "array" },
      customTypes: { type: "object" },
      customOperations: { type: "object" },
      authRules: { type: "object" },
      subscriptions: { type: "object" },
      storage: { type: "object" },
    },
    additionalProperties: false,
  }
}

function buildSchemaVersion(manifest: Manifest, sdl: string) {
  const manifestJson = stableJson(manifest)
  return {
    contractVersion: manifest.contractVersion,
    generatorVersion: GENERATOR_VERSION,
    generatedAt: new Date().toISOString(),
    hashes: {
      manifest: sha256(manifestJson),
      graphql: sha256(sdl),
    },
    sources: manifest.sources,
    packageVersions: manifest.generator.packageVersions,
  }
}

function compareGenerated(tempDir: string, outDir: string): string[] {
  const files = [
    "amplify.graphql",
    "amplify-manifest.json",
    "amplify-manifest.schema.json",
    "schema-version.json",
  ]
  const diffs: string[] = []
  for (const file of files) {
    const expected = join(outDir, file)
    const actual = join(tempDir, file)
    if (!existsSync(expected)) {
      diffs.push(`${file} is missing`)
      continue
    }
    const expectedContent = normalizeGenerated(file, readFileSync(expected, "utf8"))
    const actualContent = normalizeGenerated(file, readFileSync(actual, "utf8"))
    if (expectedContent !== actualContent) {
      diffs.push(`${file} differs`)
    }
  }
  return diffs
}

function normalizeGenerated(file: string, content: string): string {
  if (file !== "schema-version.json") {
    return content
  }
  const parsed = JSON.parse(content)
  delete parsed.generatedAt
  return stableJson(parsed)
}

function findCall(source: string, callee: string): string {
  const index = source.indexOf(`${callee}(`)
  if (index < 0) {
    throw new Error(`Could not find ${callee} call`)
  }
  return balancedFrom(source, source.indexOf("(", index))
}

function findOptionalCall(source: string, callee: string): string | null {
  const index = source.indexOf(`${callee}(`)
  if (index < 0) {
    return null
  }
  return balancedFrom(source, source.indexOf("(", index))
}

function balancedFrom(source: string, openIndex: number): string {
  const open = source[openIndex]
  const closeFor: Record<string, string> = { "(": ")", "{": "}", "[": "]" }
  if (!closeFor[open]) {
    throw new Error(`Expected an opening delimiter at ${openIndex}`)
  }
  const stack: string[] = []
  let quote: string | null = null
  let escape = false
  for (let index = openIndex; index < source.length; index += 1) {
    const char = source[index]
    if (quote) {
      if (escape) {
        escape = false
      } else if (char === "\\") {
        escape = true
      } else if (char === quote) {
        quote = null
      }
      continue
    }
    if (char === "'" || char === "\"" || char === "`") {
      quote = char
      continue
    }
    if (char === "(" || char === "{" || char === "[") {
      stack.push(closeFor[char])
    } else if (char === ")" || char === "}" || char === "]") {
      const expected = stack.pop()
      if (expected !== char) {
        throw new Error(`Unbalanced ${open}`)
      }
      if (stack.length === 0) {
        return source.slice(openIndex, index + 1)
      }
    }
  }
  throw new Error(`Unbalanced ${open}`)
}

function firstBalanced(source: string, open: "{" | "[" | "(", close: "}" | "]" | ")"): string | null {
  const start = source.indexOf(open)
  if (start < 0) {
    return null
  }
  const balanced = balancedFrom(source, start)
  if (!balanced.endsWith(close)) {
    return null
  }
  return balanced
}

function objectBody(expression: string): string {
  const start = expression.indexOf("{")
  if (start < 0) {
    throw new Error(`Expected object body in ${expression.slice(0, 80)}`)
  }
  const object = balancedFrom(expression, start)
  return object.slice(1, -1)
}

function parseObjectEntries(body: string): Array<[string, string]> {
  return splitTopLevel(stripComments(body), ",")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const colon = topLevelColon(part)
      if (colon < 0) {
        throw new Error(`Expected object entry, got: ${part.slice(0, 120)}`)
      }
      const key = part.slice(0, colon).trim().replace(/^['"]|['"]$/g, "")
      const value = part.slice(colon + 1).trim()
      return [key, value]
    })
}

function splitTopLevel(source: string, delimiter: string): string[] {
  const parts: string[] = []
  let start = 0
  let depth = 0
  let quote: string | null = null
  let escape = false
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index]
    if (quote) {
      if (escape) {
        escape = false
      } else if (char === "\\") {
        escape = true
      } else if (char === quote) {
        quote = null
      }
      continue
    }
    if (char === "'" || char === "\"" || char === "`") {
      quote = char
      continue
    }
    if (char === "(" || char === "{" || char === "[") {
      depth += 1
    } else if (char === ")" || char === "}" || char === "]") {
      depth -= 1
    } else if (char === delimiter && depth === 0) {
      parts.push(source.slice(start, index))
      start = index + 1
    }
  }
  parts.push(source.slice(start))
  return parts
}

function topLevelColon(source: string): number {
  let depth = 0
  let quote: string | null = null
  let escape = false
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index]
    if (quote) {
      if (escape) {
        escape = false
      } else if (char === "\\") {
        escape = true
      } else if (char === quote) {
        quote = null
      }
      continue
    }
    if (char === "'" || char === "\"" || char === "`") {
      quote = char
      continue
    }
    if (char === "(" || char === "{" || char === "[") {
      depth += 1
    } else if (char === ")" || char === "}" || char === "]") {
      depth -= 1
    } else if (char === ":" && depth === 0) {
      return index
    }
  }
  return -1
}

function stripComments(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/.*$/gm, "$1")
}

function stringArrayValues(source: string): string[] {
  return [...source.matchAll(/['"]([^'"]+)['"]/g)].map((match) => match[1])
}

function pluralize(modelName: string): string {
  return modelName.endsWith("s") ? modelName : `${modelName}s`
}

function pascalCase(value: string): string {
  return value
    .replace(/(^|[^a-zA-Z0-9]+)([a-zA-Z0-9])/g, (_match, _sep, char) => char.toUpperCase())
    .replace(/^[a-z]/, (char) => char.toUpperCase())
}

function scalarTypeName(_field: string): string {
  return "String"
}

function sha256(content: string): string {
  return createHash("sha256").update(content).digest("hex")
}

function contractVersionFor(...sources: string[]): string {
  return sha256([GENERATOR_VERSION, ...sources].join("\n")).slice(0, 16)
}

function packageVersions() {
  const packageJson = JSON.parse(readFileSync(packageJsonPath, "utf8"))
  const packageLock = JSON.parse(readFileSync(packageLockPath, "utf8"))
  const names = [
    "@aws-amplify/backend",
    "@aws-amplify/backend-cli",
    "@aws-amplify/data-schema",
    "@aws-amplify/schema-generator",
  ]
  return Object.fromEntries(names.map((name) => [
    name,
    packageLock.packages?.[`node_modules/${name}`]?.version
      || packageJson.dependencies?.[name]
      || packageJson.devDependencies?.[name]
      || null,
  ]))
}

function probeAmplifyRuntime() {
  return {
    available: false,
    fallback: "static-parser-for-checked-in-contract-generation",
  }
}

function writeJson(path: string, value: unknown) {
  writeFileSync(path, `${stableJson(value)}\n`)
}

function stableJson(value: unknown): string {
  return `${JSON.stringify(sortKeys(value), null, 2)}`
}

function sortKeys(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortKeys)
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, sortKeys(child)]),
    )
  }
  return value
}

main()
