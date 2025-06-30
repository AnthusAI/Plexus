// BlockRegistryInitializer
// This component imports the block registry setup to ensure blocks like TopicAnalysis are registered
// before they're used in shared report views

// Import the setup file for its side effects
import "@/components/blocks/registrySetup"; 

/**
 * A utility component to ensure the block registry is loaded.
 * Just include this component anywhere in your shared report view components
 * to fix the "Default ReportBlock not found" error.
 */
export const BlockRegistryInitializer = () => {
  // This component doesn't render anything visible
  // It just ensures the block registry is loaded via its import
  return null;
};

export default BlockRegistryInitializer; 