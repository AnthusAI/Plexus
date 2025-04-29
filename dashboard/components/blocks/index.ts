/**
 * Block registry index
 * This file imports and registers all block components with the registry
 */

import { registerBlock } from './BlockRegistry';
import ScoreInfo from './ScoreInfo';

// Register the ScoreInfo component
registerBlock('ScoreInfo', ScoreInfo as any);

// Export all block components for usage elsewhere
export { BaseBlock } from './BaseBlock';
export { default as ScoreInfo } from './ScoreInfo';
export * from './BlockRegistry'; 