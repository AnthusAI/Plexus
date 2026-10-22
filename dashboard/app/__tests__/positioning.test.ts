import { readFileSync } from 'fs'
import { join } from 'path'

const read = (file: string) => readFileSync(join(__dirname, '..', file), 'utf8')

describe('landing page positioning', () => {
  it('no longer calls Primus an AI Agent Incubator in the title, headline or social cards', () => {
    expect(read('layout.tsx')).not.toMatch(/AI Agent Incubator/)
    expect(read('page.tsx')).not.toMatch(/AI Agent Incubator/)
  })

  it('uses the classifier lab positioning from Anth.us', () => {
    const layout = read('layout.tsx')
    expect(layout).toContain('title: "Primus: the classifier lab"')
    expect(layout).toContain('The classifier lab: evaluate, deploy and improve AI with reviewer feedback.')
    expect(read('page.tsx')).toContain('headline="The classifier lab"')
  })
})
