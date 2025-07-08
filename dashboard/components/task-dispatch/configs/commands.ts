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
    // Add debug logging to see what values are being used
    console.log("Generating evaluation command with options:", options);
    
    // Make number-of-samples one of the first arguments to ensure it's processed correctly
    const args = [
      `--number-of-samples ${options.numberOfSamples}`,
      `--scorecard "${options.scorecardName}"`,
      `--score "${options.scoreName}"`,
      `--sampling-method ${options.samplingMethod}`,
      options.loadFresh ? '--fresh' : '',
      options.randomSeed ? `--random-seed ${options.randomSeed}` : '',
      options.visualize ? '--visualize' : '',
      options.logToLanggraph ? '--log-to-langgraph' : ''
    ].filter(Boolean).join(' ')
    
    const command = `evaluate ${type} ${args}`
    console.log("Generated command:", command);
    return command
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