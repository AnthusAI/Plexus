from typing import Optional, Dict
from pydantic import Field
from langgraph.graph import StateGraph
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging

class LogicalNode(BaseNode):
    """
    A node that executes arbitrary Python code without requiring Score.Result objects.
    Enables flexible state updates and custom output field mapping for general-purpose tasks.
    """
    
    class Parameters(BaseNode.Parameters):
        code: str = Field(description="Python code string defining the execution function")
        function_name: str = Field(default="execute", description="Name of function to call in the code")
        output_mapping: Optional[Dict[str, str]] = Field(default=None, description="Map function results to state fields")

    class GraphState(BaseNode.GraphState):
        # This will be extended dynamically based on output_mapping
        pass

    def __init__(self, **parameters):
        # Skip both BaseNode.__init__ and LangChainUser.__init__ since LogicalNode doesn't need LLM functionality
        # Initialize only the essential parts manually
        
        # Set up parameters directly without calling parent __init__
        self.parameters = self.Parameters(**parameters)
        
        # Initialize model to None since we don't need LLM functionality
        self.model = None
        
        # Compile the code string into a function
        namespace = {}
        exec(self.parameters.code, namespace)
        
        # Get the specified function name
        function_name = self.parameters.function_name
        self.execute_function = namespace.get(function_name)
        if not self.execute_function:
            raise ValueError(f"Code must define a '{function_name}' function")

    def get_execute_node(self):
        """Node that executes the user-defined function."""
        execute_function = self.execute_function
        parameters = self.parameters

        def execute_code(state):
            logging.info(f"<*> Entering LogicalNode execute_code node: {self.node_name}")
            if isinstance(state, dict):
                state = self.GraphState(**state)

            # Create a merged metadata dictionary that includes both the existing metadata
            # and all state attributes (excluding 'metadata' itself to avoid recursion)
            state_dict = state.model_dump()

            logging.info(f"LogicalNode state_dict: {state_dict}")

            merged_metadata = state_dict.get('metadata', {}).copy()

            # Add all state attributes directly to metadata
            for key, value in state_dict.items():
                if key != 'metadata' and key != 'text':
                    merged_metadata[key] = value
            
            # Create a context object for the function call
            context = {
                'state': state,
                'text': state.text,
                'metadata': merged_metadata,
                'parameters': parameters
            }

            logging.info(f"LogicalNode context: {context}")

            # Execute the user function
            try:
                result = execute_function(context)
                logging.info(f"LogicalNode function result: {result}")
            except Exception as e:
                logging.error(f"Error executing LogicalNode function: {str(e)}")
                return state

            # Handle the result and update state
            state_update = state.model_dump()

            if isinstance(result, dict):
                # If result is a dictionary, map its keys to state fields
                if parameters.output_mapping:
                    # Use explicit output mapping
                    for state_field, result_key in parameters.output_mapping.items():
                        if result_key in result:
                            state_update[state_field] = result[result_key]
                            logging.info(f"Mapped {result_key} -> {state_field}: {result[result_key]}")
                else:
                    # No explicit mapping, use result keys directly as state fields
                    for key, value in result.items():
                        state_update[key] = value
                        logging.info(f"Added state field {key}: {value}")
            else:
                # If result is not a dict, need explicit output mapping
                if parameters.output_mapping and len(parameters.output_mapping) == 1:
                    # Single output mapping
                    state_field = list(parameters.output_mapping.keys())[0]
                    state_update[state_field] = result
                    logging.info(f"Mapped single result to {state_field}: {result}")
                else:
                    # Store as generic result field
                    state_update['result'] = result
                    logging.info(f"Stored result: {result}")
            
            # Create the updated state
            result_state = self.GraphState(**state_update)
            
            # Log the state changes
            output_state = {}
            if isinstance(result, dict):
                if parameters.output_mapping:
                    for state_field, result_key in parameters.output_mapping.items():
                        if result_key in result:
                            output_state[state_field] = result[result_key]
                else:
                    output_state.update(result)
            else:
                if parameters.output_mapping and len(parameters.output_mapping) == 1:
                    state_field = list(parameters.output_mapping.keys())[0]
                    output_state[state_field] = result
                else:
                    output_state['result'] = result
            
            logging.info(f"LogicalNode output_state: {output_state}")
            
            # Log the state and get a new state object with updated node_results
            updated_state = self.log_state(result_state, {}, output_state)
            
            return updated_state

        return execute_code

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Add core nodes to the workflow."""
        workflow.add_node(self.node_name, self.get_execute_node())
        return workflow