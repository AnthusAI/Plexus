#!/usr/bin/env node

// Simple script to run the performance test
const { execSync } = require('child_process');
const path = require('path');

console.log('Running Scorecard Performance Test...');
console.log('====================================');

try {
  // Compile the TypeScript file first
  console.log('Compiling TypeScript...');
  execSync('npx tsc --esModuleInterop dashboard/scripts/test-scorecard-performance.ts', { stdio: 'inherit' });
  
  // Run the compiled JavaScript file
  console.log('\nExecuting performance test...');
  execSync('node dashboard/scripts/test-scorecard-performance.js', { stdio: 'inherit' });
  
  console.log('\n====================================');
  console.log('Performance test completed successfully!');
} catch (error) {
  console.error('Error running performance test:', error.message);
  process.exit(1);
} 