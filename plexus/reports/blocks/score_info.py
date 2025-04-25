from typing import Any, Dict, Optional

from .base import BaseReportBlock


class ScoreInfoBlock(BaseReportBlock):
    """
    Generates a block of information about a specific Score.
    
    Config:
        scoreId (str): The ID of the Score to display.
        include_variant (bool, optional): Whether to include variant details.
                                         Defaults to False.
    """

    def generate(
        self, config: Dict[str, Any], params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        score_id = config.get("scoreId")
        if not score_id:
            # In a real implementation, we might raise an error or return
            # a specific error structure.
            return {"error": "scoreId is required in the block configuration."}

        include_variant = config.get("include_variant", False)

        # --- Mock Data Fetching ---
        # In a real implementation, this would involve fetching the Score
        # object from the database or via an API call using score_id.
        mock_score_data = {
            "id": score_id,
            "name": f"Mock Score {score_id[:4]}...",
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
        if not include_variant and "variant" in mock_score_data:
            del mock_score_data["variant"]

        # Structure the output data
        output_data = {
            "type": "ScoreInfo", # Identify the type of data for rendering
            "data": mock_score_data,
        }

        return output_data 