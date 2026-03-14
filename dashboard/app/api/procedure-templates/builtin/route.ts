import { NextResponse } from 'next/server'

import { loadBuiltInProcedureTemplates } from '@/lib/builtin-procedure-templates'

export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    const templates = await loadBuiltInProcedureTemplates()
    return NextResponse.json({ templates })
  } catch (error) {
    console.error('Failed to load built-in procedure templates:', error)
    return NextResponse.json(
      { error: 'Failed to load built-in procedure templates' },
      { status: 500 }
    )
  }
}
