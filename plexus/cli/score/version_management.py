"""
Score version management utilities.

This module provides DRY, reusable functions for creating and managing score versions,
with proper parent version tracking and change detection.
"""

import logging
import yaml
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def create_score_version_with_parent(
    score_id: str,
    client,
    code_content: str,
    guidelines: Optional[str] = None,
    parent_version_id: Optional[str] = None,
    note: Optional[str] = None,
    branch: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new score version with proper parent tracking and change detection.

    This function implements intelligent version creation:
    1. Compares new content against parent version
    2. Only creates new version if content has changed
    3. Properly sets parentVersionId for version lineage
    4. Supports branches for experimental variants

    Args:
        score_id: ID of the score to create version for
        client: PlexusDashboardClient instance
        code_content: The YAML code content as a string
        guidelines: Optional guidelines content as a string
        parent_version_id: Optional parent version ID to compare against.
                          If None, uses champion version as parent.
        note: Optional version note
        branch: Optional branch name for this version

    Returns:
        Dict containing:
            - success: bool
            - version_id: str (new version ID if created, existing if no changes)
            - message: str (success/error message)
            - skipped: bool (true if no changes detected)
            - parent_version_id: str (the parent version used)
            - is_new: bool (true if new version was created)
    """
    try:
        # Validate YAML code content if provided
        if code_content:
            try:
                yaml.safe_load(code_content)
            except yaml.YAMLError as e:
                return {
                    "success": False,
                    "error": "INVALID_YAML",
                    "message": f"Invalid YAML code: {str(e)}"
                }

        # If no parent version specified, use champion version
        if not parent_version_id:
            champion_query = f"""
            query GetScoreChampionVersion {{
                getScore(id: "{score_id}") {{
                    championVersionId
                }}
            }}
            """
            champion_result = client.execute(champion_query)
            if champion_result and 'getScore' in champion_result:
                parent_version_id = champion_result['getScore'].get('championVersionId')

            if not parent_version_id:
                logger.info(f"No champion version found for score {score_id}, creating first version")
                # No parent version exists - this is the first version
                # We'll create it without comparison
                return _create_new_version(
                    score_id=score_id,
                    client=client,
                    code_content=code_content,
                    guidelines=guidelines,
                    parent_version_id=None,
                    note=note or "Initial version",
                    branch=branch
                )

        # Get current content from parent version for comparison
        current_yaml = ''
        current_guidelines = ''

        version_query = f"""
        query GetScoreVersionContent {{
            getScoreVersion(id: "{parent_version_id}") {{
                configuration
                guidelines
            }}
        }}
        """

        version_result = client.execute(version_query)
        if version_result and 'getScoreVersion' in version_result:
            current_version_data = version_result['getScoreVersion']
            current_yaml = (current_version_data.get('configuration') or '').strip()
            current_guidelines = (current_version_data.get('guidelines') or '').strip()

        # Compare content
        new_yaml = (code_content or '').strip()
        new_guidelines = (guidelines or '').strip()

        if new_yaml == current_yaml and new_guidelines == current_guidelines:
            logger.info(f"No changes detected for score {score_id} compared to parent version {parent_version_id}, skipping version creation")
            return {
                "success": True,
                "version_id": parent_version_id,
                "message": f"No changes detected, skipping version creation",
                "skipped": True,
                "parent_version_id": parent_version_id,
                "is_new": False
            }

        # Content has changed - create new version
        return _create_new_version(
            score_id=score_id,
            client=client,
            code_content=code_content,
            guidelines=guidelines,
            parent_version_id=parent_version_id,
            note=note or "Updated configuration",
            branch=branch
        )

    except Exception as e:
        error_msg = f"Error creating version for score {score_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": "UNEXPECTED_ERROR",
            "message": error_msg
        }


def _create_new_version(
    score_id: str,
    client,
    code_content: str,
    guidelines: Optional[str],
    parent_version_id: Optional[str],
    note: str,
    branch: Optional[str]
) -> Dict[str, Any]:
    """
    Internal function to actually create a new score version via GraphQL.

    Args:
        score_id: Score ID
        client: API client
        code_content: YAML configuration
        guidelines: Optional guidelines markdown
        parent_version_id: Optional parent version ID
        note: Version note
        branch: Optional branch name

    Returns:
        Dict with success status and version details
    """
    mutation = """
    mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
        createScoreVersion(input: $input) {
            id
            configuration
            createdAt
            updatedAt
            note
            branch
            parentVersionId
            score {
                id
                championVersionId
            }
        }
    }
    """

    version_input = {
        'scoreId': score_id,
        'configuration': code_content,
        'note': note,
        'isFeatured': True  # Mark as featured by default
    }

    if guidelines:
        version_input['guidelines'] = guidelines

    # Include parent version if available
    if parent_version_id:
        version_input['parentVersionId'] = parent_version_id

    # Add branch if provided (empty string means main branch)
    if branch and branch.strip():
        version_input['branch'] = branch.strip()

    result = client.execute(mutation, {'input': version_input})

    if not result or 'createScoreVersion' not in result:
        error_details = result.get('errors', 'Unknown error') if result else 'No response'
        return {
            "success": False,
            "error": "VERSION_CREATION_FAILED",
            "message": f"Failed to create new score version: {error_details}"
        }

    new_version = result['createScoreVersion']
    new_version_id = new_version['id']

    logger.info(f"Successfully created new version {new_version_id} for score {score_id} with parent {parent_version_id}")

    return {
        "success": True,
        "version_id": new_version_id,
        "message": f"Successfully created new version",
        "skipped": False,
        "parent_version_id": parent_version_id,
        "is_new": True,
        "created_at": new_version.get('createdAt'),
        "branch": new_version.get('branch')
    }


def get_version_from_local_yaml(score_config: Dict[str, Any]) -> Optional[str]:
    """
    Extract the version ID from a local score YAML configuration.

    The version field in local YAML files represents the champion version ID,
    which serves as the parent for new versions.

    Args:
        score_config: Score configuration dictionary (from YAML)

    Returns:
        Version ID string, or None if not present
    """
    return score_config.get('version')
