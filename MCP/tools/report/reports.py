#!/usr/bin/env python3
"""
Report management tools for Plexus MCP server
"""
import os
import json
from io import StringIO
from typing import Union, List, Dict, Optional, Any
from fastmcp import FastMCP
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from shared.setup import logger
from shared.utils import get_default_account_id, get_report_url

def register_report_tools(mcp: FastMCP):
    """Register report management tools with the MCP server"""
    
    @mcp.tool()
    async def plexus_reports_list(
        report_configuration_id: Optional[str] = None,
        limit: Optional[int] = 10
    ) -> Union[str, List[Dict]]:
        """
        Lists reports from the Plexus Dashboard. Can be filtered by report configuration ID.
        
        Parameters:
        - report_configuration_id: Optional ID of the report configuration
        - limit: Maximum number of reports to return (default 10)
        
        Returns:
        - A list of reports matching the filter criteria, sorted by createdAt in descending order (newest first)
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Import plexus CLI inside function to keep startup fast
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.dashboard.api.client import PlexusDashboardClient
            except ImportError as e:
                logger.error(f"ImportError: {str(e)}", exc_info=True)
                return f"Error: Failed to import Plexus modules: {str(e)}"
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                logger.warning("Missing API credentials. Ensure .env file is loaded.")
                return "Error: Missing API credentials. API_URL or API_KEY not set in environment."
            
            # Create dashboard client
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create dashboard client."

            # Build filter conditions
            filter_conditions = []
            
            # Always use default account
            default_account_id = get_default_account_id()
            if default_account_id:
                filter_conditions.append(f'accountId: {{eq: "{default_account_id}"}}')
                logger.info("Using default account for report listing")
            else:
                logger.warning("No default account ID available for filtering reports")
            
            limit_val = limit if limit is not None else 10
            
            # If we have a report configuration ID, use the specific GSI for it
            if report_configuration_id:
                # Use GSI by reportConfigurationId and createdAt for more efficient queries
                query = f"""
                query ListReportsByConfig {{
                    listReportByReportConfigurationIdAndCreatedAt(
                        reportConfigurationId: "{report_configuration_id}",
                        sortDirection: DESC,
                        limit: {limit_val}
                    ) {{
                        items {{
                            id
                            name
                            createdAt
                            updatedAt
                            reportConfigurationId
                            accountId
                            taskId
                        }}
                    }}
                }}
                """
                
                logger.info(f"Executing listReportByReportConfigurationIdAndCreatedAt query")
                response = client.execute(query)
                
                if response.get('errors'):
                    error_details = json.dumps(response['errors'], indent=2)
                    logger.error(f"listReportByReportConfigurationIdAndCreatedAt query returned errors: {error_details}")
                    return f"Error from listReportByReportConfigurationIdAndCreatedAt query: {error_details}"
                    
                reports_data = response.get('listReportByReportConfigurationIdAndCreatedAt', {}).get('items', [])
            else:
                # No specific report configuration - use GSI by accountId and updatedAt for sorting
                if default_account_id:
                    query = f"""
                    query ListReportsByAccountAndUpdatedAt {{
                        listReportByAccountIdAndUpdatedAt(
                            accountId: "{default_account_id}",
                            sortDirection: DESC,
                            limit: {limit_val}
                        ) {{
                            items {{
                                id
                                name
                                createdAt
                                updatedAt
                                reportConfigurationId
                                accountId
                                taskId
                            }}
                        }}
                    }}
                    """
                    
                    logger.info(f"Executing listReportByAccountIdAndUpdatedAt query")
                    response = client.execute(query)
                    
                    if response.get('errors'):
                        error_details = json.dumps(response['errors'], indent=2)
                        logger.error(f"listReportByAccountIdAndUpdatedAt query returned errors: {error_details}")
                        return f"Error from listReportByAccountIdAndUpdatedAt query: {error_details}"
                        
                    reports_data = response.get('listReportByAccountIdAndUpdatedAt', {}).get('items', [])
                else:
                    # Fallback to basic listReports without sorting if no account ID
                    query = f"""
                    query ListReports {{
                        listReports(
                            limit: {limit_val}
                        ) {{
                            items {{
                                id
                                name
                                createdAt
                                updatedAt
                                reportConfigurationId
                                accountId
                                taskId
                            }}
                        }}
                    }}
                    """
                    
                    logger.info(f"Executing basic listReports query (no account filter)")
                    response = client.execute(query)
                    
                    if response.get('errors'):
                        error_details = json.dumps(response['errors'], indent=2)
                        logger.error(f"listReports query returned errors: {error_details}")
                        return f"Error from listReports query: {error_details}"
                        
                    reports_data = response.get('listReports', {}).get('items', [])
            
            if not reports_data:
                if report_configuration_id:
                    return f"No reports found for report configuration ID: {report_configuration_id}"
                else:
                    return "No reports found."
                
            return reports_data
        except Exception as e:
            logger.error(f"Error listing reports: {str(e)}", exc_info=True)
            return f"Error listing reports: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during list_plexus_reports: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_report_info(report_id: str) -> Union[str, Dict[str, Any]]:
        """
        Gets detailed information for a specific report, including its output and any generated blocks.
        
        Parameters:
        - report_id: The unique ID of the report
        
        Returns:
        - Detailed information about the report
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Import plexus CLI inside function to keep startup fast
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.dashboard.api.client import PlexusDashboardClient
            except ImportError as e:
                logger.error(f"ImportError: {str(e)}", exc_info=True)
                return f"Error: Failed to import Plexus modules: {str(e)}"
            
            # Check if we have the necessary credentials
            api_url = os.environ.get('PLEXUS_API_URL', '')
            api_key = os.environ.get('PLEXUS_API_KEY', '')
            
            if not api_url or not api_key:
                return "Error: Missing API credentials. API_URL or API_KEY not set in environment."
            
            # Create the client
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create dashboard client."

            # Build and execute the query
            query = f"""
            query GetReport {{
                getReport(id: "{report_id}") {{
                    id
                    name
                    createdAt
                    updatedAt
                    parameters
                    output
                    accountId
                    reportConfigurationId
                    taskId
                    reportBlocks {{
                        items {{
                            id
                            reportId
                            name
                            position
                            type
                            output
                            log
                            createdAt
                            updatedAt
                        }}
                    }}
                }}
            }}
            """
            logger.info(f"Executing getReport query for ID: {report_id}")
            response = client.execute(query)

            if response.get('errors'):
                error_details = json.dumps(response['errors'], indent=2)
                logger.error(f"getReport query returned errors: {error_details}")
                return f"Error from getReport query: {error_details}"

            report_data = response.get('getReport')
            if not report_data:
                return f"Error: Report with ID '{report_id}' not found."
                
            # Add URL to the report data
            report_data['url'] = get_report_url(report_id)
            
            return report_data
        except Exception as e:
            logger.error(f"Error getting report details for ID '{report_id}': {str(e)}", exc_info=True)
            return f"Error getting report details: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during get_plexus_report_details: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_report_last(
        report_configuration_id: Optional[str] = None
    ) -> Union[str, Dict[str, Any]]:
        """
        Gets full details for the most recent report, optionally filtered by report configuration ID.
        
        Parameters:
        - report_configuration_id: Optional ID of the report configuration to filter by
        
        Returns:
        - Detailed information about the most recent report
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # First, list reports to find the latest one's ID
            reports = await plexus_reports_list(
                report_configuration_id=report_configuration_id,
                limit=1
            )
            
            # Handle error string response
            if isinstance(reports, str) and reports.startswith("Error:"):
                return reports
                
            # Handle empty response
            if not reports or (isinstance(reports, list) and len(reports) == 0):
                return "No reports found to determine the latest one."
                
            # Parse JSON if we got a JSON string
            if isinstance(reports, str):
                try:
                    reports = json.loads(reports)
                except:
                    return f"Error: Unexpected response format from list_plexus_reports: {reports}"
            
            # Get the latest report ID
            if not isinstance(reports, list) or len(reports) == 0 or not reports[0].get('id'):
                return "Error: Could not extract ID from the latest report."
            
            latest_report_id = reports[0]['id']
            logger.info(f"Found latest report ID: {latest_report_id}")
            
            # Get the full report details
            report_details = await plexus_report_info(report_id=latest_report_id)
            
            # If report_details is already a string (error message), return it directly
            if isinstance(report_details, str):
                return report_details
                
            # Add the URL if not already present
            if isinstance(report_details, dict) and 'url' not in report_details:
                report_details['url'] = get_report_url(latest_report_id)
                
            return report_details
            
        except Exception as e:
            logger.error(f"Error getting latest report: {str(e)}", exc_info=True)
            return f"Error getting latest report: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during get_latest_plexus_report: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout

    @mcp.tool()
    async def plexus_report_configurations_list() -> Union[str, List[Dict]]:
        """
        List all report configurations in reverse chronological order.
        
        Returns:
        - Array of report configuration objects with name, id, description, and updatedAt fields
        """
        # Temporarily redirect stdout to capture any unexpected output
        old_stdout = sys.stdout
        temp_stdout = StringIO()
        sys.stdout = temp_stdout
        
        try:
            # Import plexus CLI inside function to keep startup fast
            try:
                from plexus.cli.shared.client_utils import create_client as create_dashboard_client
                from plexus.dashboard.api.client import PlexusDashboardClient
            except ImportError as e:
                logger.error(f"ImportError: {str(e)}", exc_info=True)
                return f"Error: Failed to import Plexus modules: {str(e)}"
            
            # Get the client
            client = create_dashboard_client()
            if not client:
                return "Error: Could not create dashboard client."
            
            # Get the default account ID
            actual_account_id = get_default_account_id()
            if not actual_account_id:
                return "Error: Could not determine default account ID. Please check that PLEXUS_ACCOUNT_KEY is set in environment."
                
            logger.info("Listing report configurations")
            
            # Build and execute the query
            query = f"""
            query MyQuery {{
              listReportConfigurationByAccountIdAndUpdatedAt(
                accountId: "{actual_account_id}"
                sortDirection: DESC
              ) {{
                items {{
                  description
                  name
                  id
                  updatedAt
                }}
                nextToken
              }}
            }}
            """
            
            response = client.execute(query)
            
            if 'errors' in response:
                error_details = json.dumps(response['errors'], indent=2)
                logger.error(f"Dashboard query for report configurations returned errors: {error_details}")
                return f"Error from Dashboard query for report configurations: {error_details}"
            
            # Extract data from response
            configs_data = response.get('listReportConfigurationByAccountIdAndUpdatedAt', {}).get('items', [])
            
            # If no configurations found, try a different approach
            if not configs_data:
                # Try with slightly different parameters as a fallback
                retry_query = f"""
                query RetryQuery {{
                  listReportConfigurations(filter: {{ accountId: {{ eq: "{actual_account_id}" }} }}, limit: 20) {{
                    items {{
                      id
                      name
                      description
                      updatedAt
                    }}
                  }}
                }}
                """
                retry_response = client.execute(retry_query)
                
                if 'listReportConfigurations' in retry_response:
                    configs_data = retry_response['listReportConfigurations'].get('items', [])
                    
            # Format each configuration
            if not configs_data:
                return "No report configurations found."
            
            formatted_configs = []
            for config in configs_data:
                formatted_configs.append({
                    "id": config.get("id"),
                    "name": config.get("name"),
                    "description": config.get("description"),
                    "updatedAt": config.get("updatedAt")
                })
            
            logger.info(f"Successfully retrieved {len(formatted_configs)} report configurations")
            return formatted_configs
        
        except Exception as e:
            logger.error(f"Error listing report configurations: {str(e)}", exc_info=True)
            return f"Error listing report configurations: {str(e)}"
        finally:
            # Check if anything was written to stdout
            captured_output = temp_stdout.getvalue()
            if captured_output:
                logger.warning(f"Captured unexpected stdout during list_plexus_report_configurations: {captured_output}")
            # Restore original stdout
            sys.stdout = old_stdout