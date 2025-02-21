import { TaskAction } from '../types'

interface EvaluationOptions {
  scorecardName: string
  scoreName: string
  numberOfSamples: number
  samplingMethod: 'random' | 'sequential'
  loadFresh: boolean
  randomSeed?: number
  visualize: boolean
  logToLanggraph: boolean
}

interface DemoOptions {
  // Add any demo-specific options here
}

interface OptimizationOptions {
  // Add any optimization-specific options here
}

// Command type definitions
type SimpleCommandDef = {
  type: 'simple'
  generate: () => string
}

type ComplexCommandDef<T> = {
  type: 'complex'
  generate: (options: T) => string
}

// Helper function to create commands
const createSimpleCommand = (generator: () => string): SimpleCommandDef => ({
  type: 'simple',
  generate: generator
})

const createComplexCommand = <T>(generator: (options: T) => string): ComplexCommandDef<T> => ({
  type: 'complex',
  generate: generator
})

// Evaluation command helpers
const createEvaluationCommand = (type: string) => {
  return createComplexCommand<EvaluationOptions>((options) => {
    const args = [
      `--scorecard-name ${options.scorecardName}`,
      `--score-name "${options.scoreName}"`,
      `--number-of-samples ${options.numberOfSamples}`,
      `--sampling-method ${options.samplingMethod}`,
      options.loadFresh ? '--load-fresh' : '',
      options.randomSeed ? `--random-seed ${options.randomSeed}` : '',
      options.visualize ? '--visualize' : '',
      options.logToLanggraph ? '--log-to-langgraph' : ''
    ].filter(Boolean).join(' ')
    
    return `evaluate ${type} ${args}`
  })
}

// Command definitions
export const commands = {
  demo: createSimpleCommand(() => 'command demo'),

  evaluation: {
    accuracy: createEvaluationCommand('accuracy'),
    consistency: createEvaluationCommand('consistency'),
    alignment: createEvaluationCommand('alignment')
  },

  optimization: createSimpleCommand(() => 'optimize')
} as const

// Type helpers
export type CommandType = keyof typeof commands
export type EvaluationType = keyof typeof commands.evaluation 