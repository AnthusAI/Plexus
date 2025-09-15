# Proposal: Loop Controller Node Type

## Background

The CMG - EDU v1.0 scorecard includes a critical "TCPA Consent" score which validates if proper consent was obtained for each school mentioned in a call. This score is particularly complex because the TCPA (Telephone Consumer Protection Act) validation has different rules based on the school type, portal origin, and other metadata factors.

Currently, the score attempts to handle all possible validation scenarios in a single flow with complex prompts that ask the LLM to handle multiple branching logical conditions. The metadata extractor has to identify all schools requiring consent and determine the specific TCPA format required for each one, which can vary significantly.

## Problem

The current implementation faces a fundamental challenge: we're asking a single LLM call to handle too many conditional logic branches simultaneously. This creates unreliable results, as the model struggles to:

1. Keep track of multiple schools in a single call
2. Apply different validation rules to each school
3. Handle the 5 different TCPA format rules
4. Generate accurate consolidated judgments

The complexity is evident in the current metadata extraction logic:

```yaml
# Current logical rules the LLM is trying to implement
system_message: |-
  You are a metadata processor for TCPA consent verification. Your job is to extract all relevant information needed for TCPA validation from the provided metadata and return it in a structured format.

  Special TCPA Format Rules:
  1. If Portal = "Transfer" → Use Warm Transfer TCPA format
  2. If Portal = "LEADCURRENTV2" → Use the school-specific TCPA from metadata
  3. If the school is "Florida Tech Online Undergrad" OR "Intellitec" OR "Edufficient" → Use the school-specific TCPA from metadata
  4. If the school is "Aviation Institute of Maintenance" or "AIM" → Use the school-specific TCPA
  5. Otherwise → Use standard TCPA format

  For each school, determine the exact TCPA format required and extract the specific TCPA text when applicable in the metadata.
```

After this extraction, subsequent validation nodes must apply these rules correctly across all schools, which proves too complex for reliable LLM performance. We need an orchestration approach that simplifies each LLM call to focus on a single school with a single set of validation rules.

## Solution

### Overview

We propose implementing a new `LoopController` node type that enables iteration over collections in the state, with controlled routing based on item attributes. This allows us to:

1. Process each school individually through dedicated validation paths
2. Apply the appropriate validation rules based on school-specific factors
3. Collect results from each validation
4. Aggregate the results into a final determination

The `LoopController` would manage the iteration state, routing logic, and results collection automatically. Each validator node would handle only a single validation scenario, greatly simplifying the LLM's task and increasing reliability.

### Proposed YAML Configuration

The TCPA Consent score would be reconfigured as follows:

```yaml
- name: TCPA Consent
  description: TCPA Consent Verification
  id: 45407
  class: LangGraphScore
  model_provider: ChatOpenAI
  model_name: gpt-4o-mini-2024-07-18
  graph:
    # Loop controller to iterate through each school
    # Directly accesses metadata.schools without requiring an extractor
    - name: tcpa_router
      class: LoopController
      collection_path: metadata.schools
      item_name: current_school
      routing_logic: |
        def route_item(school):
          """Route each school based on its attributes"""
          if school.get('origin') == "Transfer":
            return "warm_transfer_path"
          elif school.get('origin') == "LEADCURRENTV2":
            return "school_specific_path"
          elif school.get('name') in ["Florida Tech Online Undergrad", "Intellitec", "Edufficient"]:
            return "school_specific_path"
          elif school.get('name') in ["Aviation Institute of Maintenance", "AIM"]:
            return "aim_specific_path"
          else:
            return "standard_path"
      conditions:
        - value: "LOOP_DONE"
          node: "END"
          output:
            value: aggregation_result
            explanation: aggregation_explanation
        - value: "standard_path"
          node: "standard_validator" 
        - value: "warm_transfer_path"
          node: "warm_transfer_validator"
        - value: "school_specific_path"
          node: "school_specific_validator"
        - value: "aim_specific_path"
          node: "aim_specific_validator"
      aggregation_code: |
        def aggregate_results(parameters, input):
          """Aggregate the results of all schools"""
          item_results = input.metadata.get('item_results', [])
          
          # Check if any schools failed
          failed_schools = [r['item'].get('name', 'Unknown school') for r in item_results if r['result'] == 'No']
          
          if failed_schools:
            return Score.Result(
              parameters=parameters,
              value="No",
              metadata={
                "explanation": f"TCPA verification failed for: {', '.join(failed_schools)}"
              }
            )
          else:
            return Score.Result(
              parameters=parameters,
              value="Yes",
              metadata={
                "explanation": "All schools properly received TCPA consent"
              }
            )

    # Standard format validator
    - name: standard_validator
      class: Classifier
      valid_classes:
        - 'Yes'
        - 'No'
      system_message: |-
        You are validating TCPA consent using the STANDARD format for a SINGLE school.
        
        Required elements for STANDARD format:
        1. FULL NAME of school
        2. ALL contact methods (email, text, AND phone)
        3. Automated technology notification
        4. Statement that consent is not required to purchase goods/services
        5. Statement that consent can be withdrawn anytime
        6. Phrase "Message/data rates may apply"
      user_message: |-
        School: {{current_school.name}}
        
        Transcript: {{text}}
        
        Validate if this SPECIFIC school received proper TCPA consent according to the STANDARD format requirements.
        First provide your reasoning (2-3 sentences maximum), then your conclusion (YES or NO).
      edge:
        node: "tcpa_router_collector"

    # Warm transfer validator
    - name: warm_transfer_validator
      class: Classifier
      valid_classes:
        - 'Yes'
        - 'No'
      system_message: |-
        You are validating TCPA consent using the WARM TRANSFER format for a SINGLE school.
        
        Required elements for WARM TRANSFER format:
        1. FULL NAME of school
        2. ALL contact methods (email, text, AND phone)
        3. Automated technology notification
        4. Statement that consent is not required to purchase goods/services
        5. Statement that consent can be withdrawn anytime
        6. Phrase "Message/data rates may apply"
        7. Statement that transferred calls are also recorded
      user_message: |-
        School: {{current_school.name}}
        
        Transcript: {{text}}
        
        Validate if this SPECIFIC school received proper TCPA consent according to the WARM TRANSFER format requirements.
        First provide your reasoning (2-3 sentences maximum), then your conclusion (YES or NO).
      edge:
        node: "tcpa_router_collector"

    # School-specific validator
    - name: school_specific_validator
      class: Classifier
      valid_classes:
        - 'Yes'
        - 'No'
      system_message: |-
        You are validating TCPA consent using a SCHOOL-SPECIFIC format for a SINGLE school.
        You must check if the specific TCPA text was used for this school.
      user_message: |-
        School: {{current_school.name}}
        School-specific TCPA text: {{current_school.tcpa}}
        
        Transcript: {{text}}
        
        Validate if this SPECIFIC school received proper TCPA consent using its SCHOOL-SPECIFIC format.
        First provide your reasoning (2-3 sentences maximum), then your conclusion (YES or NO).
      edge:
        node: "tcpa_router_collector"

    # AIM-specific validator
    - name: aim_specific_validator
      class: Classifier
      valid_classes:
        - 'Yes'
        - 'No'
      system_message: |-
        You are validating TCPA consent for Aviation Institute of Maintenance (AIM) which has SPECIAL requirements.
      user_message: |-
        School: {{current_school.name}}
        
        Transcript: {{text}}
        
        Validate if AIM received proper TCPA consent according to its special requirements.
        First provide your reasoning (2-3 sentences maximum), then your conclusion (YES or NO).
      edge:
        node: "tcpa_router_collector"
```

### Proposed LoopController Implementation

```python
from typing import Optional, Dict, Any, List
from pydantic import Field, BaseModel
from langgraph.graph import StateGraph, END
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.scores.Score import Score
from plexus.LangChainUser import LangChainUser
import pydantic

class LoopController(BaseNode):
    """
    A node that manages iteration over a collection with state tracking,
    routing to different paths based on item type, and aggregating results.
    """
    
    class Parameters(BaseNode.Parameters):
        collection_path: str = Field(description="Path to the collection to iterate over (e.g., 'metadata.schools')")
        item_name: str = Field(description="Name to use for current item in state")
        # Optional routing logic - if not provided, will just increment through items
        routing_logic: Optional[str] = Field(default=None, description="Optional Python code for routing items to paths")
        # Make conditions required since we need them for routing
        conditions: list = Field(description="List of conditions for routing results")
        # Optional aggregation logic - runs when loop is complete
        aggregation_code: Optional[str] = Field(default=None, description="Optional Python code for aggregating results")

    class GraphState(BaseNode.GraphState):
        current_index: int = 0
        total_items: int = 0
        current_item: Optional[Any] = None
        item_results: List[Dict[str, Any]] = Field(default_factory=list)
        # Dynamic classification used for routing
        classification: Optional[str] = None 
        # For final result
        aggregation_result: Optional[str] = None
        aggregation_explanation: Optional[str] = None

    def __init__(self, **parameters):
        super().__init__(**parameters)
        
        # Compile the routing logic if provided
        if self.parameters.routing_logic:
            routing_namespace = {}
            exec(self.parameters.routing_logic, routing_namespace)
            self.route_function = routing_namespace.get('route_item')
            if not self.route_function:
                raise ValueError("Routing logic must define a 'route_item' function")
        else:
            self.route_function = None
            
        # Compile the aggregation logic if provided
        if self.parameters.aggregation_code:
            agg_namespace = {'Score': Score}
            exec(self.parameters.aggregation_code, agg_namespace)
            self.aggregate_function = agg_namespace.get('aggregate_results')
            if not self.aggregate_function:
                raise ValueError("Aggregation code must define an 'aggregate_results' function")
        else:
            self.aggregate_function = None

    def get_loop_controller_node(self):
        """Node that manages the iteration state and routing."""
        collection_path = self.parameters.collection_path
        item_name = self.parameters.item_name
        route_function = self.route_function
        aggregate_function = self.aggregate_function
        parameters = Score.Parameters(**self.parameters.model_dump())

        def execute_controller(state):
            logging.info(f"=== Loop Controller: {self.node_name} ===")
            
            if isinstance(state, dict):
                state = self.GraphState(**state)
                
            # First run - initialize the loop state
            if not hasattr(state, 'current_index') or state.current_index == 0:
                # Extract collection from nested path (e.g., metadata.schools)
                collection = state
                for part in collection_path.split('.'):
                    if hasattr(collection, part):
                        collection = getattr(collection, part)
                    elif isinstance(collection, dict) and part in collection:
                        collection = collection[part]
                    else:
                        logging.error(f"Cannot access {part} in {collection}")
                        collection = []
                        break
                
                # Initialize state
                state_dict = state.model_dump()
                state_dict.update({
                    'current_index': 0,
                    'total_items': len(collection) if collection else 0,
                    'item_results': [],
                    'current_item': collection[0] if collection and len(collection) > 0 else None
                })
                state = self.GraphState(**state_dict)
                logging.info(f"Loop initialized with {state.total_items} items")
            
            # Check if we're done with all items
            if state.current_index >= state.total_items:
                logging.info("Loop complete - all items processed")
                
                # Apply aggregation if provided
                if aggregate_function:
                    score_input = Score.Input(
                        text=state.text,
                        metadata={
                            **state.metadata if state.metadata else {},
                            'item_results': state.item_results
                        }
                    )
                    result = aggregate_function(parameters, score_input)
                    state_dict = state.model_dump()
                    state_dict.update({
                        'classification': "LOOP_DONE",
                        'value': result.value,
                        'explanation': result.metadata.get('explanation'),
                        'aggregation_result': result.value,
                        'aggregation_explanation': result.metadata.get('explanation')
                    })
                    state = self.GraphState(**state_dict)
                else:
                    # Default aggregation - all items must be "Yes" for overall "Yes"
                    all_passed = all(r.get('result') == "Yes" for r in state.item_results)
                    state_dict = state.model_dump()
                    state_dict.update({
                        'classification': "LOOP_DONE", 
                        'value': "Yes" if all_passed else "No",
                        'explanation': "All items passed" if all_passed else "One or more items failed"
                    })
                    state = self.GraphState(**state_dict)
                
                logging.info(f"Final result: {state.value}")
                return state
            
            # Process current item
            collection = state
            for part in collection_path.split('.'):
                if hasattr(collection, part):
                    collection = getattr(collection, part)
                elif isinstance(collection, dict) and part in collection:
                    collection = collection[part]
                else:
                    logging.error(f"Cannot access {part} in {collection}")
                    collection = []
                    break
            
            # Get current item
            current_item = collection[state.current_index] if collection else None
            
            # If we have a routing function, use it to determine the path
            if route_function and current_item:
                route = route_function(current_item)
                logging.info(f"Item {state.current_index} routed to {route}")
            else:
                # Default to just "CONTINUE" for simple iteration
                route = "CONTINUE"
            
            # Update state with current item
            state_dict = state.model_dump()
            state_dict.update({
                'current_item': current_item,
                'classification': route  # Use route as classification for conditional edges
            })
            return self.GraphState(**state_dict)
        
        return execute_controller
    
    def get_results_collector_node(self):
        """Node that collects results and updates loop state for next iteration."""
        item_name = self.parameters.item_name
        
        def collect_results(state):
            logging.info(f"=== Results Collector for {self.node_name} ===")
            
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            # Update item_results with the result of the current item processing
            state_dict = state.model_dump()
            current_item = state_dict.get('current_item')
            current_result = {
                'item': current_item,
                'item_index': state.current_index,
                'result': state_dict.get('value', 'Unknown'),
                'explanation': state_dict.get('explanation', '')
            }
            
            # Add the new result
            item_results = state.item_results.copy()
            item_results.append(current_result)
            
            # Update for next iteration
            state_dict.update({
                'item_results': item_results,
                'current_index': state.current_index + 1,
                'classification': "NEXT_ITEM"  # Route back to controller
            })
            
            logging.info(f"Item {state.current_index} processed, moving to next item")
            return self.GraphState(**state_dict)
            
        return collect_results

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Add core nodes to the workflow."""
        # Add the main controller node
        workflow.add_node(self.node_name, self.get_loop_controller_node())
        
        # Add a collector node to update state after processing each item
        results_collector_name = f"{self.node_name}_collector"
        workflow.add_node(results_collector_name, self.get_results_collector_node())
        
        return workflow
```

This approach dramatically simplifies each validator's job to focus on a single school with clearly defined rules, while automatically handling the complexity of routing, state management, and results aggregation through the `LoopController` node.