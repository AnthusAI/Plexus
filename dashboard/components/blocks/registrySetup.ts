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
import FeedbackAlignment from './FeedbackAlignment';
import ExplanationAnalysis from './ExplanationAnalysis';
import ScorecardReport from './ScorecardReport';
import ScoreInfo from './ScoreInfo';
import TopicAnalysis from './TopicAnalysis';
import CostAnalysis from './CostAnalysis';
import VectorTopicMemory from './VectorTopicMemory';
import ActionItems from './ActionItems';
import FeedbackContradictions from './FeedbackContradictions';
import FeedbackAlignmentTimeline from './FeedbackAlignmentTimeline';
import FeedbackVolumeTimeline from './FeedbackVolumeTimeline';
import CorrectionRate from './CorrectionRate';
import AcceptanceRate from './AcceptanceRate';
import AcceptanceRateTimeline from './AcceptanceRateTimeline';
import RecentFeedback from './RecentFeedback';
import ScoreChampionVersionTimeline from './ScoreChampionVersionTimeline';

// Register all block components
// Register the default block handler first
registerBlock('default', ReportBlock);

// Register specific block types - use type casting to satisfy BlockComponent interface
registerBlock('ScorecardReport', ScorecardReport as BlockComponent);
registerBlock('FeedbackAlignment', FeedbackAlignment as BlockComponent);
registerBlock('FeedbackAnalysis', FeedbackAlignment as BlockComponent);
registerBlock('ExplanationAnalysis', ExplanationAnalysis as BlockComponent);
registerBlock('text', TextBlock as BlockComponent);
registerBlock('ScoreInfo', ScoreInfo as BlockComponent);
registerBlock('TopicAnalysis', TopicAnalysis as BlockComponent); 
registerBlock('CostAnalysis', CostAnalysis as BlockComponent);
registerBlock('VectorTopicMemory', VectorTopicMemory as BlockComponent);
registerBlock('ActionItems', ActionItems as BlockComponent);
registerBlock('FeedbackContradictions', FeedbackContradictions as BlockComponent);
registerBlock('FeedbackAlignmentTimeline', FeedbackAlignmentTimeline as BlockComponent);
registerBlock('FeedbackVolumeTimeline', FeedbackVolumeTimeline as BlockComponent);
registerBlock('CorrectionRate', CorrectionRate as BlockComponent);
registerBlock('AcceptanceRate', AcceptanceRate as BlockComponent);
registerBlock('AcceptanceRateTimeline', AcceptanceRateTimeline as BlockComponent);
registerBlock('RecentFeedback', RecentFeedback as BlockComponent);
registerBlock('ScoreChampionVersionTimeline', ScoreChampionVersionTimeline as BlockComponent);
