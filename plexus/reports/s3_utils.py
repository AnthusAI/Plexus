import os
import logging
import tempfile
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

logger = logging.getLogger(__name__)

# Default bucket name for report block details S3 storage
# This should match the resource name in amplify/storage/resource.ts
DEFAULT_BUCKET_NAME = "reportblockdetails-production"

def get_bucket_name():
    """
    Get the S3 bucket name for report block details from environment variables
    or fall back to the default.
    """
    return os.environ.get("AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME", DEFAULT_BUCKET_NAME)

def upload_report_block_file(report_block_id, file_name, content, content_type=None):
    """
    Upload a file to the report block details S3 bucket using the format expected by Amplify Gen2.
    
    Args:
        report_block_id: ID of the report block this file belongs to
        file_name: Name of the file to create
        content: Bytes content to upload
        content_type: Optional MIME type for the file
    
    Returns:
        The S3 path (key) for the file, formatted for Amplify Gen2
    """
    bucket_name = get_bucket_name()
    
    logger.info(f"Starting S3 upload for block {report_block_id}, file {file_name}")
    logger.info(f"Using S3 bucket: {bucket_name}")
    
    # Check if bucket name exists
    if not bucket_name:
        logger.error("S3 bucket name is empty or None! Check environment variables or default config.")
        raise ValueError("S3 bucket name is missing")
    
    # Check if content is empty
    if not content:
        logger.warning(f"Content for file {file_name} is empty or None!")
    
    s3_client = boto3.client('s3')
    
    # Format path according to Amplify Gen2 expectations
    # The path should match what's defined in amplify/storage/resource.ts
    s3_key = f"reportblocks/{report_block_id}/{file_name}"
    
    logger.info(f"Creating temporary file for content (content length: {len(content) if content else 0})")
    
    # Create a temporary file to upload from
    with tempfile.NamedTemporaryFile(mode='wb+', suffix=f"_{file_name}", delete=False) as temp_file:
        temp_file_path = temp_file.name
        logger.info(f"Created temp file at {temp_file_path}")
        # Encode content to bytes if it's a string, otherwise use as is (assuming it's already bytes or None)
        if isinstance(content, str):
            temp_file.write(content.encode('utf-8'))
        elif content is not None: # It's bytes or some other non-None type
            temp_file.write(content)
        else: # content is None
            temp_file.write(b"") # Write empty bytes if content is None
    
    try:
        # Set up extra args if content type is specified
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
            
        logger.info(f"Starting S3 upload to s3://{bucket_name}/{s3_key} with args: {extra_args}")
        
        # Upload the file to S3
        s3_client.upload_file(
            Filename=temp_file_path,
            Bucket=bucket_name, 
            Key=s3_key,
            ExtraArgs=extra_args
        )
        
        logger.info(f"Successfully uploaded {file_name} to s3://{bucket_name}/{s3_key}")
        
        # Return just the S3 path (key) as specified in the docstring
        return s3_key
    except ClientError as e:
        logger.error(f"AWS ClientError uploading file to S3: {str(e)}")
        logger.error(f"Error details: {e.response['Error'] if hasattr(e, 'response') else 'No response details'}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading file to S3: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        # Always remove the temporary file
        if os.path.exists(temp_file_path):
            logger.info(f"Removing temp file {temp_file_path}")
            os.remove(temp_file_path)

def add_file_to_report_block(report_block_id, file_name, content: bytes, content_type=None, client=None):
    """
    Upload a file to S3 and add its path to an existing report block's attachedFiles array.
    
    Args:
        report_block_id: ID of the existing report block
        file_name: Name of the file to create
        content: Bytes content to upload
        content_type: Optional MIME type for the file
        client: Optional PlexusDashboardClient instance
    
    Returns:
        Updated list of file paths in attachedFiles
    """
    from plexus.dashboard.api.models.report_block import ReportBlock
    
    # Upload the file to S3 and get the path
    file_path = upload_report_block_file(
        report_block_id=report_block_id,
        file_name=file_name,
        content=content,
        content_type=content_type
    )
    
    # Fetch the existing report block
    report_block = ReportBlock.get_by_id(report_block_id, client)
    if not report_block:
        logger.error(f"Report block with ID {report_block_id} not found")
        raise ValueError(f"Report block with ID {report_block_id} not found")
    
    # Log the current state
    logger.info(f"Current attachedFiles before update for block {report_block_id}: {report_block.attachedFiles}")
    
    # Get existing attachedFiles or initialize as empty list
    file_paths = []
    if report_block.attachedFiles:
        # Handle various formats that might exist in older data
        if isinstance(report_block.attachedFiles, list):
            file_paths = report_block.attachedFiles
            logger.info(f"attachedFiles is already a list with {len(file_paths)} items")
        else:
            # For backward compatibility - try to parse JSON if it's a string
            try:
                import json
                file_paths = json.loads(report_block.attachedFiles)
                logger.info(f"Successfully parsed existing attachedFiles JSON (for backward compatibility)")
                
                # Check if we have old format objects and extract just paths
                if file_paths and isinstance(file_paths[0], dict) and 'path' in file_paths[0]:
                    logger.warning(f"Converting old format attachedFiles to just paths")
                    file_paths = [item['path'] for item in file_paths]
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON or not string, just use as a single item
                logger.warning(f"Could not parse attachedFiles - treating as a single item")
                file_paths = [report_block.attachedFiles]
    
    # Add the new file path
    file_paths.append(file_path)
    
    # Update the report block - pass the array directly without JSON conversion
    report_block.update(attachedFiles=file_paths, client=client)
    logger.info(f"Updated report block {report_block_id} with attachedFiles")
    
    # Verify the update
    updated_block = ReportBlock.get_by_id(report_block_id, client)
    if updated_block:
        logger.info(f"After update, attachedFiles for block {report_block_id}: {updated_block.attachedFiles}")
    else:
        logger.warning(f"Could not verify update - block {report_block_id} not found after update")
    
    return file_paths

def download_report_block_file(s3_path, local_path=None):
    """
    Download a file from the report block details S3 bucket.
    
    Args:
        s3_path: S3 key path for the file (e.g., 'reportblocks/123/log.txt')
        local_path: Optional local path to save the file to
        
    Returns:
        The content of the file as a string, and the local path if saved
    """
    bucket_name = get_bucket_name()
    s3_client = boto3.client('s3')
    
    # Create a temporary file if no local path provided
    if not local_path:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            local_path = temp_file.name
            
    try:
        # Download the file
        s3_client.download_file(
            Bucket=bucket_name,
            Key=s3_path,
            Filename=local_path
        )
        
        # Read the file contents
        with open(local_path, 'r') as f:
            content = f.read()
            
        logger.info(f"Successfully downloaded s3://{bucket_name}/{s3_path}")
        return content, local_path
    
    except ClientError as e:
        logger.error(f"Error downloading file from S3: {e}")
        if os.path.exists(local_path) and not local_path:
            os.remove(local_path)
        raise
    except Exception as e:
        logger.error(f"Unexpected error downloading file: {e}")
        if os.path.exists(local_path) and not local_path:
            os.remove(local_path)
        raise 

def check_s3_bucket_access(bucket_name=None):
    """
    Diagnostic function to check if the S3 bucket exists and is accessible.
    
    Args:
        bucket_name: Name of the bucket to check, or None to use the default
        
    Returns:
        Dict with diagnostic information
    """
    if bucket_name is None:
        bucket_name = get_bucket_name()
        
    logger.info(f"Running S3 bucket access check for: {bucket_name}")
    
    try:
        s3_client = boto3.client('s3')
        
        # Check if we can list the bucket
        logger.info("Attempting to list objects in bucket...")
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=1,
            Prefix="reportblocks/"
        )
        
        # Log the response status
        logger.info(f"List operation succeeded. Found {response.get('KeyCount', 0)} objects")
        
        # Try to create a test file
        test_content = f"S3 bucket access test at {datetime.now().isoformat()}"
        test_key = f"reportblocks/test/access_check_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
        
        logger.info(f"Attempting to upload test file: {test_key}")
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(test_content)
        
        try:
            # Upload the file
            s3_client.upload_file(
                Filename=temp_file_path,
                Bucket=bucket_name,
                Key=test_key
            )
            logger.info(f"Successfully uploaded test file: {test_key}")
            
            # Try to download it
            download_path = tempfile.mktemp()
            s3_client.download_file(
                Bucket=bucket_name,
                Key=test_key,
                Filename=download_path
            )
            
            with open(download_path, 'r') as f:
                downloaded_content = f.read()
                
            logger.info(f"Successfully downloaded test file. Content matches: {downloaded_content == test_content}")
            
            # Clean up
            s3_client.delete_object(
                Bucket=bucket_name,
                Key=test_key
            )
            logger.info(f"Successfully deleted test file: {test_key}")
            
            # Make sure to clean up local files
            if os.path.exists(download_path):
                os.remove(download_path)
            
            return {
                "bucket_exists": True,
                "can_list": True,
                "can_write": True,
                "can_read": True,
                "can_delete": True,
                "bucket_name": bucket_name
            }
            
        except Exception as e:
            logger.error(f"Error during upload/download/delete test: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "bucket_exists": True,
                "can_list": True,
                "can_write": False,
                "can_read": False,
                "can_delete": False,
                "error": str(e),
                "bucket_name": bucket_name
            }
            
        finally:
            # Clean up the temp file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except ClientError as e:
        logger.error(f"AWS ClientError during S3 bucket check: {str(e)}")
        error_code = e.response.get('Error', {}).get('Code')
        
        if error_code == 'NoSuchBucket':
            return {
                "bucket_exists": False,
                "error": f"Bucket '{bucket_name}' does not exist",
                "bucket_name": bucket_name
            }
        elif error_code == 'AccessDenied':
            return {
                "bucket_exists": True,  # Probably exists if access was denied
                "error": f"Access denied to bucket '{bucket_name}'",
                "bucket_name": bucket_name
            }
        else:
            return {
                "error": f"AWS error: {error_code} - {str(e)}",
                "bucket_name": bucket_name
            }
    
    except Exception as e:
        logger.error(f"Unexpected error during S3 bucket check: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        return {
            "error": f"Unexpected error: {str(e)}",
            "bucket_name": bucket_name
        } 