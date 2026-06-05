import unittest
from unittest.mock import patch, MagicMock
import os
import tempfile
from plexus.reports.s3_utils import (
    create_s3_client,
    get_bucket_name,
    upload_report_block_file,
    download_report_block_file,
)

class TestS3Utils(unittest.TestCase):
    
    @patch.dict(os.environ, {"AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME": "test-bucket"}, clear=True)
    def test_get_bucket_name_with_env_var(self):
        bucket_name = get_bucket_name()
        self.assertEqual(bucket_name, "test-bucket")
        
    @patch.dict(os.environ, {}, clear=True)
    def test_get_bucket_name_default(self):
        bucket_name = get_bucket_name()
        self.assertEqual(bucket_name, "reportblockdetails-production")
        
    @patch('boto3.client')
    @patch('plexus.reports.s3_utils.get_bucket_name')
    @patch('tempfile.NamedTemporaryFile')
    @patch.dict(os.environ, {}, clear=True)
    def test_upload_report_block_file(self, mock_tempfile, mock_get_bucket, mock_boto3_client):
        # Setup mocks
        mock_get_bucket.return_value = "test-bucket"
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Create a mock temp file
        mock_file = MagicMock()
        mock_file.name = "/tmp/test_file"
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        # Call the function
        result = upload_report_block_file(
            report_block_id="test-block-id",
            file_name="test.txt",
            content="Hello, world!",
            content_type="text/plain"
        )
        
        # Assert that boto3 client was created and upload_file was called
        mock_boto3_client.assert_called_once_with("s3")
        mock_s3_client.upload_file.assert_called_once_with(
            Filename="/tmp/test_file",
            Bucket="test-bucket", 
            Key="reportblocks/test-block-id/test.txt",
            ExtraArgs={"ContentType": "text/plain"}
        )
        
        # Assert the returned structure
        self.assertEqual(result, "reportblocks/test-block-id/test.txt")
        
    @patch('boto3.client')
    @patch('plexus.reports.s3_utils.get_bucket_name')
    @patch('builtins.open', create=True)
    @patch.dict(os.environ, {}, clear=True)
    def test_download_report_block_file(self, mock_open, mock_get_bucket, mock_boto3_client):
        # Setup mocks
        mock_get_bucket.return_value = "test-bucket"
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        
        # Mock the open context manager to return a file-like object
        mock_file = MagicMock()
        mock_file.read.return_value = "Hello, world!"
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Call the function with a specified path
        file_descriptor, local_path = tempfile.mkstemp()
        os.close(file_descriptor)
        content, path = download_report_block_file(
            s3_path="reportblocks/test-block-id/test.txt",
            local_path=local_path
        )
        
        # Assert that boto3 client was created and download_file was called
        mock_boto3_client.assert_called_once_with("s3")
        mock_s3_client.download_file.assert_called_once_with(
            Bucket="test-bucket",
            Key="reportblocks/test-block-id/test.txt",
            Filename=local_path
        )
        
        # Assert the returned content
        self.assertEqual(content, "Hello, world!")
        self.assertEqual(path, local_path)

    @patch('boto3.client')
    @patch.dict(os.environ, {
        "PLEXUS_OBJECT_STORE_ENDPOINT": "http://localhost:19000",
        "PLEXUS_OBJECT_STORE_REGION": "us-east-1",
        "PLEXUS_OBJECT_STORE_FORCE_PATH_STYLE": "true",
        "PLEXUS_OBJECT_STORE_ACCESS_KEY_ID": "local-access",
        "PLEXUS_OBJECT_STORE_SECRET_ACCESS_KEY": "local-secret",
    }, clear=True)
    def test_create_s3_client_uses_local_object_store_env(self, mock_boto3_client):
        create_s3_client()

        _, kwargs = mock_boto3_client.call_args
        self.assertEqual(mock_boto3_client.call_args.args, ("s3",))
        self.assertEqual(kwargs["endpoint_url"], "http://localhost:19000")
        self.assertEqual(kwargs["region_name"], "us-east-1")
        self.assertEqual(kwargs["aws_access_key_id"], "local-access")
        self.assertEqual(kwargs["aws_secret_access_key"], "local-secret")
        self.assertEqual(kwargs["config"].s3["addressing_style"], "path")
        
if __name__ == '__main__':
    unittest.main() 
