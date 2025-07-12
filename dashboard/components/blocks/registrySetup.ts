/**
 * Block registry setup
 * This file imports all block components and registers them with the registry.
 * Import this file once in the relevant part of the application (e.g., the Reports Dashboard)
 * to ensure blocks are registered before the BlockRenderer is used.
 */

import { registerBlock } from './BlockRegistry';
import { BlockComponent } from './ReportBlock';
import ReportBlock from './ReportBlock';
import TextBlock from './TextBlock';
import FeedbackAnalysis from './FeedbackAnalysis';
import ScorecardReport from './ScorecardReport';
import ScoreInfo from './ScoreInfo';
import TopicAnalysis from './TopicAnalysis';

// Register all block components
// Register the default block handler first
registerBlock('default', ReportBlock);

// Register specific block types - use type casting to satisfy BlockComponent interface
registerBlock('ScorecardReport', ScorecardReport as BlockComponent);
registerBlock('FeedbackAnalysis', FeedbackAnalysis as BlockComponent);
registerBlock('text', TextBlock as BlockComponent);
registerBlock('ScoreInfo', ScoreInfo as BlockComponent);
registerBlock('TopicAnalysis', TopicAnalysis as BlockComponent); 