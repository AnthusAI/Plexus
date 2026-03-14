import 'server-only'

import { promises as fs } from 'fs'
import path from 'path'
import yaml from 'js-yaml'

export interface BuiltInProcedureTemplate {
  slug: string
  name: string
  description: string
  category: string
  version: string
  code: string
}

const BUILTIN_TEMPLATE_FILES = [
  { slug: 'scorecard_create', fileName: 'scorecard_create.yaml' },
  { slug: 'score_code_create', fileName: 'score_code_create.yaml' },
] as const

type ParsedProcedureConfig = {
  name?: string
  description?: string
  version?: string
}

function getProceduresDirectory(): string {
  return path.resolve(process.cwd(), '..', 'plexus', 'procedures')
}

export async function loadBuiltInProcedureTemplates(): Promise<BuiltInProcedureTemplate[]> {
  const proceduresDirectory = getProceduresDirectory()

  return Promise.all(
    BUILTIN_TEMPLATE_FILES.map(async ({ slug, fileName }) => {
      const filePath = path.join(proceduresDirectory, fileName)
      const code = await fs.readFile(filePath, 'utf8')
      const parsed = (yaml.load(code) as ParsedProcedureConfig | null) || {}

      return {
        slug,
        name: parsed.name || slug,
        description: parsed.description || '',
        category: `builtin:${slug}`,
        version: parsed.version || '1.0.0',
        code,
      }
    })
  )
}
