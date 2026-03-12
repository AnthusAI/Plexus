/**
 * This file tells TypeScript to completely skip type checking for these modules,
 * which can dramatically improve type checking performance.
 * 
 * After profiling with `npm run typecheck:profile`, add the slowest modules here.
 * Common culprits are AWS libraries, complex UI frameworks, etc.
 */

// AWS SDK (all modules)
declare module '@aws-sdk/*';
declare module '@aws-amplify/*';
declare module 'aws-amplify';
declare module '@smithy/*';

// UI libraries that can be slow
declare module '@radix-ui/*';
declare module '@nivo/*';
declare module 'framer-motion';
declare module 'recharts'; 