from typing import Any, Dict, Optional, Tuple
import json
import logging
import asyncio

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

    async def generate(
        self # config/params/client accessed via self
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetches (mock) Score data and returns it with logs."""
        self.log_messages = [] # Reset logs for this run
        final_output_data = None # Default to None

        try:
            self._log(f"Starting ScoreInfo block generation.")
            score_identifier = self.config.get("score")
            if not score_identifier:
                self._log("ERROR: 'score' identifier missing in block configuration.")
                raise ValueError("'score' is required in the block configuration.")

            include_variant = self.config.get("include_variant", False)
            self._log(f"Fetching info for score: {score_identifier}, include_variant: {include_variant}")

            # --- Mock Data Fetching ---
            # Replace with actual async API call using self.api_client
            # score_data = await self.api_client.get_score_by_identifier(score_identifier)
            # For now, use mock data:
            await asyncio.sleep(0.01) # Simulate async work
            mock_score_data = {
                "id": score_identifier,
                "name": f"Mock Score {score_identifier[:4]}...",
                "value": 0.85,
                "description": "This is a mock score description.",
                "variant": {
                    "id": "var-123",
                    "name": "Default Variant",
                } if include_variant else None,
                "createdAt": "2023-10-27T10:00:00Z",
                "updatedAt": "2023-10-27T10:05:00Z",
            }
            self._log(f"Mock data fetched successfully for {score_identifier}.")
            # --- End Mock Data Fetching ---

            # Process data
            final_data = {k: v for k, v in mock_score_data.items() if v is not None}

            # Structure the output data dictionary
            final_output_data = {
                "type": "ScoreInfo",
                "data": final_data,
            }
            self._log("ScoreInfo block generation successful.")

        except ValueError as ve:
            # Log specific config errors
             self._log(f"Configuration Error: {ve}")
            # final_output_data remains None
        except Exception as e:
            # Log unexpected errors during generation
            self._log(f"ERROR during ScoreInfo generation: {str(e)}")
            # Log traceback? Might be too verbose for block log, but useful.
            # self._log(traceback.format_exc())
            # final_output_data remains None

        # --- Format and Return --- 
        log_string = "\n".join(self.log_messages) if self.log_messages else None
        # Return the data (or None if error) and the collected logs
        return final_output_data, log_string

        # try:
        #     json_output = json.dumps(final_data, indent=2)
        #     markdown_output = f"```json\n{json_output}\n```\n"
        #     return markdown_output
        # except TypeError as e:
        #      logger.error(f"Failed to serialize score data to JSON for {score_identifier}: {e}")
        #      # Return an error string that the service layer can embed
        #      return f"<!-- Error: Failed to serialize score data for {score_identifier}: {e} -->"

        # return output_data 