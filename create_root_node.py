#!/usr/bin/env python3
"""
Quick script to create a root node for an experiment that doesn't have one.
This fixes the issue where experiments created without root nodes can't generate hypothesis nodes.
"""

import sys
import os
sys.path.append('/Users/ryan.porter/Projects/Plexus')

from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.experiment import Experiment
from plexus.dashboard.api.models.experiment_node import ExperimentNode
from plexus.dashboard.api.models.experiment_node_version import ExperimentNodeVersion

# Default YAML template for experiments
DEFAULT_EXPERIMENT_YAML = """class: "BeamSearch"

value: |
  -- Extract accuracy score from experiment node's structured data
  local score = experiment_node.value.accuracy or 0
  -- Apply cost penalty to balance performance vs efficiency  
  local penalty = (experiment_node.value.cost or 0) * 0.1
  -- Return single scalar value (higher is better)
  return score - penalty

exploration: |
  You are helping optimize an AI system through beam search experimentation.
  
  You have access to previous experiment results including their configurations, 
  performance metrics, and computed values. Your job is to suggest new experiment 
  variations that might improve performance.
  
  Based on the results so far, propose specific changes to try next. Focus on 
  modifications that could address weaknesses or build on promising directions.
  
  Generate concrete, actionable suggestions for the next experiment iteration.
"""

def create_root_node_for_experiment(experiment_id: str):
    """Create a root node for an experiment that doesn't have one."""
    
    client = PlexusDashboardClient()
    
    # Get the experiment
    experiment = Experiment.get_by_id(experiment_id, client)
    if not experiment:
        print(f"Error: Experiment {experiment_id} not found")
        return False
        
    # Check if it already has a root node
    existing_root = experiment.get_root_node()
    if existing_root:
        print(f"Experiment {experiment_id} already has a root node: {existing_root.id}")
        return True
    
    print(f"Creating root node for experiment {experiment_id}...")
    
    try:
        # Create the root node
        root_node = ExperimentNode.create(
            client=client,
            experimentId=experiment_id,
            parentNodeId=None,
            status='ACTIVE'
        )
        
        print(f"Created root node: {root_node.id}")
        
        # Create initial version with default YAML
        version = ExperimentNodeVersion.create(
            client=client,
            experimentId=experiment_id,
            nodeId=root_node.id,
            code=DEFAULT_EXPERIMENT_YAML,
            status='QUEUED',
            value={"initialized": True, "created_by": "manual_setup"}
        )
        
        print(f"Created initial version: {version.id}")
        
        # Update experiment to reference the root node
        experiment.update_root_node(root_node.id)
        
        print(f"Successfully created root node {root_node.id} for experiment {experiment_id}")
        return True
        
    except Exception as e:
        print(f"Error creating root node: {e}")
        return False

if __name__ == "__main__":
    experiment_id = "f7eafe48-ac95-4e09-9304-16340c885f4d"
    success = create_root_node_for_experiment(experiment_id)
    sys.exit(0 if success else 1)