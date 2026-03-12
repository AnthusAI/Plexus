module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: {
    '^@/components/(.*)$': '<rootDir>/components/$1',
    '^@/(.*)$': '<rootDir>/$1',
    // Mock problematic ESM modules
    '^react-markdown$': '<rootDir>/__mocks__/react-markdown.js',
    '^@number-flow/react$': '<rootDir>/__mocks__/number-flow-react.js',
    '^remark-gfm$': '<rootDir>/__mocks__/remark-gfm.js',
    '^remark-breaks$': '<rootDir>/__mocks__/remark-breaks.js',
  },
  testPathIgnorePatterns: ['<rootDir>/.next/', '<rootDir>/node_modules/'],
  transform: {
    '^.+\\.(t|j)sx?$': ['@swc/jest'],
  },
  transformIgnorePatterns: [
    'node_modules/(?!(esm-env|@number-flow|number-flow|react-markdown|remark-|unist-|unified|bail|is-plain-obj|trough|vfile|micromark|decode-named-character-reference|character-entities)/)',
  ],
  extensionsToTreatAsEsm: ['.ts', '.tsx'],
}
