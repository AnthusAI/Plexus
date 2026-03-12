# Report Block Details S3 Storage

This document explains the implementation of S3 storage for report block details in Plexus.

## Overview

Previously, all log data from report blocks was stored directly in the ReportBlock record in DynamoDB. This was limiting because:

1. DynamoDB has a maximum size limit for attributes
2. Large log output couldn't be stored effectively
3. Additional files like charts, CSV data, or other supplementary materials couldn't be attached

To solve this, we've implemented S3 storage for report block details, where:

1. The ReportBlock model includes a `attachedFiles` field that contains a JSON array of file paths
2. Each path is a string that points to the S3 key where the file is stored
3. Files are stored in the Amplify-managed S3 bucket with a structure of `reportblocks/{report_block_id}/{filename}`

## Implementation Details

### S3 Bucket

We use an Amplify-managed S3 bucket for storing report block details. This bucket is defined in `dashboard/amplify/storage/resource.ts`:

```typescript
export const reportBlockDetails = defineStorage({
  name: 'reportBlockDetails',
  access: (allow) => ({
    'reportblocks/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ]
  })
});
```

### ReportBlock Model

The ReportBlock model in `plexus/dashboard/api/models/report_block.py` includes an `attachedFiles` field that stores a JSON array of file paths:

```python
class ReportBlock(BaseModel):
    # ... other fields ...
    attachedFiles = attr.Field(null=True)  # JSON array of file paths (strings)
```

### File Upload

Files are uploaded to S3 and added to the ReportBlock's `attachedFiles` field using the `add_file_to_report_block` function in `plexus/reports/s3_utils.py`:

```python
def add_file_to_report_block(report_block_id, file_name, content, content_type=None, client=None):
    # Upload the file to S3 and get the path
    file_path = upload_report_block_file(
        report_block_id=report_block_id,
        file_name=file_name,
        content=content,
        content_type=content_type
    )
    
    # Get existing attachedFiles
    report_block = ReportBlock.get_by_id(report_block_id, client)
    file_paths = []
    if report_block.attachedFiles:
        file_paths = json.loads(report_block.attachedFiles)
    
    # Add the new file path
    file_paths.append(file_path)
    
    # Update the report block
    report_block.update(attachedFiles=json.dumps(file_paths), client=client)
    
    return file_paths
```

### Using Amplify Storage APIs

In the frontend, we use the Amplify Storage APIs to get URLs for the files stored in S3:

```typescript
import { Storage } from 'aws-amplify';

// Get URLs for files
const getFileUrls = async (filePaths: string[]) => {
  return Promise.all(
    filePaths.map(async (path) => {
      const url = await Storage.get(path);
      return { path, url };
    })
  );
};
```

## Important Notes

1. The `attachedFiles` field should always be a JSON array of string paths
2. When adding new file attachments, always fetch the existing `attachedFiles`, append to it, and update
3. Never store the file content directly in the `attachedFiles` field
4. Use the Amplify Storage APIs to work with the files in the frontend

## Backend Components

### S3 Storage Definition

The S3 bucket is defined in Amplify:

```typescript
// dashboard/amplify/storage/resource.ts
export const reportBlockDetails = defineStorage({
  name: 'reportBlockDetails',
  access: (allow) => ({
    'reportblocks/*': [
      allow.guest.to(['read']),
      allow.authenticated.to(['read', 'write', 'delete'])
    ]
  })
});
```

### ReportBlock Model

The ReportBlock model includes a `attachedFiles` field:

```typescript
// dashboard/amplify/data/resource.ts
ReportBlock: a
    .model({
        // ... other fields ...
        attachedFiles: a.json(), // JSON array of file paths (strings)
    })
```

### Python Utilities

New utility functions to manage S3 storage:

1. **`plexus/reports/s3_utils.py`**:
   - `upload_report_block_file`: Upload a file to S3 and return file info
   - `add_file_to_report_block`: Upload a file and update the ReportBlock record
   - `download_report_block_file`: Download and read a file from S3

2. **BaseReportBlock** enhancement:
   - `attach_detail_file`: Method to attach a file to a report block

3. **Service Integration**:
   - Updated `service.py` to automatically store log files in S3

## Frontend Components

### BlockDetails Component

A new React component to display and interact with files:

```typescript
// dashboard/components/reports/BlockDetails.tsx
const BlockDetails: React.FC<BlockDetailsProps> = ({ block }) => {
  // Renders a list of detail files with view/download buttons
  // Fetch pre-signed URLs for accessing S3 files
  // Displays text file content in a dialog
}
```

### ReportTask Integration

The ReportTask component has been updated to:
1. Include `attachedFiles` in GraphQL queries
2. Render the BlockDetails component for each report block

## Usage

### Automatic Log Storage

Logs are automatically stored in S3 when report blocks are created. The service will:

1. Create a ReportBlock record
2. Upload the log content to S3 as `log.txt`
3. Update the ReportBlock record with the file reference

### Custom File Attachment

In report block code, you can attach custom files:

```python
# Example of attaching a custom file in a report block
async def generate(self):
    # ... generate report block data ...
    
    # After getting the report block ID, attach files
    if report_block_id:
        self.attach_detail_file(
            report_block_id=report_block_id,
            file_name="data.csv",
            content=csv_content,
            content_type="text/csv"
        )
    
    return output_data, log_summary
```

## Example JSON

The `attachedFiles` field contains a JSON array like:

```json
[
  "reportblocks/01234567-89ab-cdef-0123-456789abcdef/log.txt",
  "reportblocks/01234567-89ab-cdef-0123-456789abcdef/data.csv"
]
```

## Configuration

The S3 bucket name is determined by:

1. Environment variable: `AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME`
2. Default fallback: `reportblockdetails-production`

## Testing

The implementation includes unit tests:
- `plexus/reports/s3_utils_test.py`

## Future Enhancements

Potential future enhancements:
- Support for larger binary files (images, PDFs)
- Automatic file expiration/cleanup
- Direct file upload from the frontend
- Enhanced file previews for more file types 