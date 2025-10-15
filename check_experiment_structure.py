#!/usr/bin/env python3
"""Check the structure of experiment nodes and versions to debug issues."""

import sys
import os
sys.path.append('/Users/ryan.porter/Projects/Plexus')

def check_with_env_vars():
    """Check experiment structure using environment variables."""
    
    # Set environment variables from what we know works
    os.environ['PLEXUS_API_URL'] = 'https://7ubj23ym5vekxagab2damu2euy.appsync-api.us-west-2.amazonaws.com/graphql'
    os.environ['PLEXUS_API_KEY'] = 'da2-mrwmpcj2xjb3piioidfe76zkdq'
    os.environ['PLEXUS_ACCOUNT_KEY'] = 'call-criteria'
    
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.dashboard.api.models.experiment import Experiment
    from plexus.dashboard.api.models.experiment_node import ExperimentNode
    
    client = PlexusDashboardClient()
    experiment_id = "f7eafe48-ac95-4e09-9304-16340c885f4d"
    
    try:
        print(f"=== EXPERIMENT STRUCTURE FOR {experiment_id} ===")
        
        # Get experiment
        experiment = Experiment.get_by_id(experiment_id, client)
        print(f"Experiment: {experiment.id}")
        print(f"Root node ID: {experiment.rootNodeId}")
        
        # Get all nodes
        all_nodes = ExperimentNode.list_by_experiment(experiment_id, client)
        print(f"\nTotal nodes: {len(all_nodes)}")
        
        for i, node in enumerate(all_nodes):
            print(f"\n--- Node {i+1}: {node.id} ---")
            print(f"  Parent: {node.parentNodeId}")
            print(f"  Status: {node.status}")
            print(f"  Created: {node.createdAt}")
            
            # Get versions for this node
            versions = node.get_versions()
            print(f"  Versions: {len(versions)}")
            
            for j, version in enumerate(versions):
                print(f"    Version {j+1}: {version.id}")
                print(f"      Status: {version.status}")
                print(f"      Hypothesis: {version.hypothesis if hasattr(version, 'hypothesis') else 'N/A'}")
                print(f"      Insight: {version.insight if hasattr(version, 'insight') else 'N/A'}")
                
                # Check value content
                if version.value:
                    hypothesis_in_value = version.value.get('hypothesis', 'Not found')
                    created_by = version.value.get('created_by', 'Not found')
                    print(f"      Value.hypothesis: {hypothesis_in_value}")
                    print(f"      Value.created_by: {created_by}")
                else:
                    print(f"      Value: None")
                    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_with_env_vars()