from langchain.tools import tool

@tool
def list_plexus_report_configurations(accountId: str = None) -> str:
    """
    List all report configurations for the specified account in reverse chronological order.
    
    Args:
        accountId (str, optional): The ID of the account to list report configurations for.
            If not provided, the current account ID from the context will be used.
    
    Returns:
        str: JSON string containing a list of report configuration names sorted by most recently updated first.
    """
    from plexus.dashboard.api.models.report_configuration import ReportConfiguration
    import json
    import logging
    import traceback

    logger = logging.getLogger(__name__)
    
    try:
        if accountId is None:
            from plexus.mcp.context import get_context
            context = get_context()
            accountId = context.get_account_id()
            client = context.get_api_client()
            logger.debug(f"Using account ID from context: {accountId}")
        else:
            from plexus.dashboard.api.client import get_api_client
            client = get_api_client()
            logger.debug(f"Using provided account ID: {accountId}")
        
        logger.info(f"Listing report configurations for account {accountId}")
        
        try:
            result = ReportConfiguration.list_by_account_id(
                account_id=accountId,
                client=client,
                limit=50
            )
            logger.debug(f"Retrieved {len(result.get('items', []))} report configurations")
        except Exception as e:
            logger.error(f"GraphQL error listing report configurations: {e}")
            logger.error(traceback.format_exc())
            return json.dumps({"error": f"GraphQL query failed: {str(e)}"})
        
        configs = []
        for config in result.get('items', []):
            try:
                configs.append({
                    "name": config.name,
                    "id": config.id,
                    "description": config.description,
                    "updatedAt": config.updatedAt.isoformat() if config.updatedAt else None
                })
                logger.debug(f"Added configuration: {config.name}")
            except Exception as e:
                logger.error(f"Error processing configuration: {e}")
                
        logger.info(f"Successfully processed {len(configs)} report configurations")
        return json.dumps(configs, ensure_ascii=True)
    
    except Exception as e:
        error_msg = f"Error listing report configurations: {str(e)}"
        logger.exception(error_msg)
        logger.error(traceback.format_exc())
        return json.dumps({"error": error_msg}, ensure_ascii=True) 