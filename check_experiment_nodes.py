#!/usr/bin/env python3
"""Check if hypothesis nodes were created in the experiment."""

import sys
import os
sys.path.append('/Users/ryan.porter/Projects/Plexus')

from plexus.cli.shared.client_utils import create_client
from plexus.cli.experiment.service import ExperimentService

def check_nodes():
    """Check how many nodes exist in the experiment."""
    
    client = create_client()
    service = ExperimentService(client)
    
    experiment_id = "f7eafe48-ac95-4e09-9304-16340c885f4d"
    
    try:
        experiment_info = service.get_experiment_info(experiment_id)
        if experiment_info:
            print(f"Experiment: {experiment_info.experiment.id}")
            print(f"Node count: {experiment_info.node_count}")
            print(f"Version count: {experiment_info.version_count}")
            print(f"Root node: {experiment_info.root_node.id if experiment_info.root_node else 'None'}")
            
            if experiment_info.node_count > 1:
                print("✅ HYPOTHESIS NODES WERE CREATED!")
                print("The AI agent successfully generated experiment variations.")
            else:
                print("❌ Only root node exists - no hypothesis nodes were created yet.")
                
        else:
            print("Experiment not found")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_nodes()