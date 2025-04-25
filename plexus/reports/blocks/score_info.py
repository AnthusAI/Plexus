from typing import Any, Dict, Optional
import json
import logging

from .base import BaseReportBlock

logger = logging.getLogger(__name__)


class ScoreInfo(BaseReportBlock):
    """
    Generates a block of information about a specific Score.
    
    Config:
        score (str): The ID or name of the Score to display. 
                     (Note: Current mock implementation uses this as ID)
        include_variant (bool, optional): Whether to include variant details.
                                         Defaults to False.
    """

    def generate(
        self, config: Dict[str, Any], params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        # score_id = config.get("scoreId") # OLD
        score_identifier = config.get("score") # NEW
        # if not score_id: # OLD
        if not score_identifier: # NEW
            # In a real implementation, we might raise an error or return
            # a specific error structure.
            # return {"error": "scoreId is required in the block configuration."} # OLD
            return {"error": "'score' is required in the block configuration."} # NEW

        include_variant = config.get("include_variant", False)

        # --- Mock Data Fetching ---
        # In a real implementation, this would involve fetching the Score
        # object from the database or via an API call using score_identifier.
        mock_score_data = {
            # "id": score_id, # OLD
            "id": score_identifier, # NEW - Mock assumes identifier is the ID for now
            # "name": f"Mock Score {score_id[:4]}...", # OLD
            "name": f"Mock Score {score_identifier[:4]}...", # NEW
            "value": 0.85, # Example value
            "description": "This is a mock score description.",
            "variant": {
                "id": "var-123",
                "name": "Default Variant",
            } if include_variant else None,
            "createdAt": "2023-10-27T10:00:00Z",
            "updatedAt": "2023-10-27T10:05:00Z",
        }
        # --- End Mock Data Fetching ---

        # Remove variant if not included and it's None
        # Also remove None values before converting to JSON for cleaner output
        final_data = {k: v for k, v in mock_score_data.items() if v is not None}
        # if not include_variant and "variant" in mock_score_data:
        #     del mock_score_data["variant"]

        # Structure the output data as a dictionary
        # This dictionary will be serialized to JSON by the service layer.
        output_data = {
            "type": "ScoreInfo", # Identify the type of data for potential rendering hints
            "data": final_data,
        }
        
        # The service layer is responsible for JSON serialization.
        # Just return the dictionary.
        return output_data
        
        # try:
        #     json_output = json.dumps(final_data, indent=2)
        #     markdown_output = f"```json\n{json_output}\n```\n"
        #     return markdown_output
        # except TypeError as e:
        #      logger.error(f"Failed to serialize score data to JSON for {score_identifier}: {e}")
        #      # Return an error string that the service layer can embed
        #      return f"<!-- Error: Failed to serialize score data for {score_identifier}: {e} -->"

        # return output_data 