/**
 * YAML DSL Linter Test Runner
 * 
 * Runs test cases against both Python and TypeScript implementations
 * to ensure consistency between backends and frontends.
 */

import { createLinterForContext } from '../../dashboard/lib/yaml-linter-schemas'
import type { LintResult, LintMessage } from '../../dashboard/lib/yaml-linter'

interface TestCase {
  name: string
  description: string
  context: 'score' | 'data-source'
  input: string
  expected: {
    is_valid: boolean
    error_count?: number
    warning_count?: number
    info_count?: number
    messages?: Array<{
      code: string
      level: string
    }>
  }
  tags: string[]
}

interface TestSuite {
  score_tests: TestCase[]
  data_source_tests: TestCase[]
  integration_tests: TestCase[]
}

interface TestResult {
  testCase: TestCase
  result: LintResult
  passed: boolean
  errors: string[]
}

class YamlLinterTestRunner {
  private testSuite: TestSuite

  constructor(testSuite: TestSuite) {
    this.testSuite = testSuite
  }

  /**
   * Run all test cases
   */
  async runAllTests(): Promise<TestResult[]> {
    const results: TestResult[] = []

    // Run score tests
    for (const testCase of this.testSuite.score_tests) {
      const result = await this.runTestCase(testCase)
      results.push(result)
    }

    // Run data source tests
    for (const testCase of this.testSuite.data_source_tests) {
      const result = await this.runTestCase(testCase)
      results.push(result)
    }

    // Run integration tests
    for (const testCase of this.testSuite.integration_tests) {
      const result = await this.runTestCase(testCase)
      results.push(result)
    }

    return results
  }

  /**
   * Run tests filtered by tags
   */
  async runTestsByTags(tags: string[]): Promise<TestResult[]> {
    const allTestCases = [
      ...this.testSuite.score_tests,
      ...this.testSuite.data_source_tests,
      ...this.testSuite.integration_tests
    ]

    const filteredTests = allTestCases.filter(testCase =>
      tags.some(tag => testCase.tags.includes(tag))
    )

    const results: TestResult[] = []
    for (const testCase of filteredTests) {
      const result = await this.runTestCase(testCase)
      results.push(result)
    }

    return results
  }

  /**
   * Run a single test case
   */
  async runTestCase(testCase: TestCase): Promise<TestResult> {
    try {
      const linter = createLinterForContext(testCase.context)
      const result = linter.lint(testCase.input)

      const errors = this.validateResult(testCase, result)
      const passed = errors.length === 0

      return {
        testCase,
        result,
        passed,
        errors
      }
    } catch (error) {
      return {
        testCase,
        result: {
          is_valid: false,
          messages: [],
          error_count: 1,
          warning_count: 0,
          info_count: 0
        },
        passed: false,
        errors: [`Test execution failed: ${error instanceof Error ? error.message : String(error)}`]
      }
    }
  }

  /**
   * Validate test result against expected outcomes
   */
  private validateResult(testCase: TestCase, result: LintResult): string[] {
    const errors: string[] = []

    // Check validity
    if (result.is_valid !== testCase.expected.is_valid) {
      errors.push(`Expected is_valid: ${testCase.expected.is_valid}, got: ${result.is_valid}`)
    }

    // Check error count
    if (testCase.expected.error_count !== undefined) {
      if (result.error_count !== testCase.expected.error_count) {
        errors.push(`Expected error_count: ${testCase.expected.error_count}, got: ${result.error_count}`)
      }
    }

    // Check warning count
    if (testCase.expected.warning_count !== undefined) {
      if (result.warning_count !== testCase.expected.warning_count) {
        errors.push(`Expected warning_count: ${testCase.expected.warning_count}, got: ${result.warning_count}`)
      }
    }

    // Check info count
    if (testCase.expected.info_count !== undefined) {
      if (result.info_count !== testCase.expected.info_count) {
        errors.push(`Expected info_count: ${testCase.expected.info_count}, got: ${result.info_count}`)
      }
    }

    // Check specific messages
    if (testCase.expected.messages) {
      for (const expectedMessage of testCase.expected.messages) {
        const foundMessage = result.messages.find(m => 
          m.code === expectedMessage.code && m.level === expectedMessage.level
        )
        if (!foundMessage) {
          errors.push(`Expected message with code '${expectedMessage.code}' and level '${expectedMessage.level}' not found`)
        }
      }
    }

    return errors
  }

  /**
   * Generate test report
   */
  generateReport(results: TestResult[]): string {
    const totalTests = results.length
    const passedTests = results.filter(r => r.passed).length
    const failedTests = totalTests - passedTests

    let report = `\n=== YAML DSL Linter Test Report ===\n`
    report += `Total Tests: ${totalTests}\n`
    report += `Passed: ${passedTests}\n`
    report += `Failed: ${failedTests}\n`
    report += `Success Rate: ${((passedTests / totalTests) * 100).toFixed(1)}%\n\n`

    if (failedTests > 0) {
      report += `=== Failed Tests ===\n`
      results.filter(r => !r.passed).forEach(result => {
        report += `\n❌ ${result.testCase.name}\n`
        report += `   Description: ${result.testCase.description}\n`
        report += `   Context: ${result.testCase.context}\n`
        report += `   Tags: ${result.testCase.tags.join(', ')}\n`
        result.errors.forEach(error => {
          report += `   Error: ${error}\n`
        })
      })
    }

    if (passedTests > 0) {
      report += `\n=== Passed Tests ===\n`
      results.filter(r => r.passed).forEach(result => {
        report += `✅ ${result.testCase.name} (${result.testCase.context})\n`
      })
    }

    return report
  }

  /**
   * Generate detailed results for debugging
   */
  generateDetailedReport(results: TestResult[]): string {
    let report = `\n=== Detailed Test Results ===\n`

    results.forEach((result, index) => {
      report += `\n--- Test ${index + 1}: ${result.testCase.name} ---\n`
      report += `Description: ${result.testCase.description}\n`
      report += `Context: ${result.testCase.context}\n`
      report += `Tags: ${result.testCase.tags.join(', ')}\n`
      report += `Status: ${result.passed ? '✅ PASSED' : '❌ FAILED'}\n`
      
      if (!result.passed) {
        report += `Errors:\n`
        result.errors.forEach(error => {
          report += `  - ${error}\n`
        })
      }

      report += `\nInput YAML:\n`
      report += result.testCase.input.split('\n').map(line => `  ${line}`).join('\n') + '\n'

      report += `\nActual Result:\n`
      report += `  is_valid: ${result.result.is_valid}\n`
      report += `  error_count: ${result.result.error_count}\n`
      report += `  warning_count: ${result.result.warning_count}\n`
      report += `  info_count: ${result.result.info_count}\n`

      if (result.result.messages.length > 0) {
        report += `  messages:\n`
        result.result.messages.forEach(msg => {
          report += `    - ${msg.level}: ${msg.code} - ${msg.title}\n`
          if (msg.message) {
            report += `      ${msg.message}\n`
          }
        })
      }

      report += `\nExpected Result:\n`
      report += `  is_valid: ${result.testCase.expected.is_valid}\n`
      if (result.testCase.expected.error_count !== undefined) {
        report += `  error_count: ${result.testCase.expected.error_count}\n`
      }
      if (result.testCase.expected.warning_count !== undefined) {
        report += `  warning_count: ${result.testCase.expected.warning_count}\n`
      }
      if (result.testCase.expected.info_count !== undefined) {
        report += `  info_count: ${result.testCase.expected.info_count}\n`
      }
      if (result.testCase.expected.messages) {
        report += `  expected_messages:\n`
        result.testCase.expected.messages.forEach(msg => {
          report += `    - ${msg.level}: ${msg.code}\n`
        })
      }
    })

    return report
  }
}

// Example usage and demo function
export async function runDemo(): Promise<void> {
  // Sample test cases for demonstration
  const demoTestSuite: TestSuite = {
    score_tests: [
      {
        name: "Valid basic score",
        description: "A simple valid score configuration",
        context: "score",
        input: `name: "Test Score"\nkey: "test_score"\ndescription: "A test score"`,
        expected: {
          is_valid: true,
          error_count: 0,
          warning_count: 0
        },
        tags: ["demo", "valid"]
      },
      {
        name: "Missing required field",
        description: "Score missing required key field",
        context: "score",
        input: `name: "Test Score"\ndescription: "Missing key field"`,
        expected: {
          is_valid: false,
          error_count: 1,
          messages: [{ code: "REQUIRED_FIELD_KEY", level: "error" }]
        },
        tags: ["demo", "invalid"]
      }
    ],
    data_source_tests: [
      {
        name: "Valid data source",
        description: "A simple valid data source configuration",
        context: "data-source",
        input: `type: "file"\nname: "Test Data Source"\nformat: "csv"`,
        expected: {
          is_valid: true,
          error_count: 0,
          warning_count: 0
        },
        tags: ["demo", "valid"]
      }
    ],
    integration_tests: []
  }

  const runner = new YamlLinterTestRunner(demoTestSuite)
  const results = await runner.runAllTests()
  
  console.log(runner.generateReport(results))
  console.log(runner.generateDetailedReport(results))
}

export { YamlLinterTestRunner, type TestCase, type TestSuite, type TestResult }