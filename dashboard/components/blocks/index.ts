/**
 * Block registry index
 * This file exports block-related components and utilities.
 * Registration is handled in registrySetup.ts
 */

// Export components and utilities
export { default as ReportBlock } from './ReportBlock';
export type { ReportBlockProps, BlockComponent } from './ReportBlock';
export { default as ScoreInfo } from './ScoreInfo';
export { default as TextBlock } from './TextBlock';
export { default as FeedbackAnalysis } from './FeedbackAnalysis';
export { BlockRenderer } from './BlockRegistry';
export type { BlockRendererProps } from './BlockRegistry';
export { getBlock, hasBlock, getRegisteredBlockTypes } from './BlockRegistry';

// DO NOT REGISTER BLOCKS HERE - See registrySetup.ts 