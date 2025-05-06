/**
 * Block registry setup
 * This file imports all block components and registers them with the registry.
 * Import this file once in the relevant part of the application (e.g., the Reports Dashboard)
 * to ensure blocks are registered before the BlockRenderer is used.
 */

import { registerBlock } from './BlockRegistry';
import ScoreInfo from './ScoreInfo';
import ReportBlock from './ReportBlock';
import TextBlock from './TextBlock'; // Assuming TextBlock exists and should be registered

// Register all block components
console.log("Running Block Registry Setup..."); // Add log for debugging
registerBlock('ScoreInfo', ScoreInfo as any); // Keep the 'as any' for now if it was there
registerBlock('default', ReportBlock);
// If TextBlock registers itself, remove its import and registration here.
// Otherwise, ensure it's registered correctly:
// registerBlock('TextBlock', TextBlock); 

console.log("Block Registry Setup Complete."); 