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
export { default as ExplanationAnalysis } from './ExplanationAnalysis';
export { default as ScorecardReport } from './ScorecardReport';
export { default as ActionItems } from './ActionItems';
export { default as FeedbackAlignmentTimeline } from './FeedbackAlignmentTimeline';
export { default as CorrectionRate } from './CorrectionRate';
export { default as AcceptanceRate } from './AcceptanceRate';
export { default as AcceptanceRateTimeline } from './AcceptanceRateTimeline';
export { default as RecentFeedback } from './RecentFeedback';
export { BlockRenderer } from './BlockRegistry';
export type { BlockRendererProps } from './BlockRegistry';
export { getBlock, hasBlock, getRegisteredBlockTypes } from './BlockRegistry';

export { default as FeedbackContradictions } from './FeedbackContradictions';

// DO NOT REGISTER BLOCKS HERE - See registrySetup.ts 
