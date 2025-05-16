# Report Block Details S3 Storage

This document explains the implementation of S3 storage for report block details in Plexus.

## Overview

Previously, all log data from report blocks was stored directly in the ReportBlock record in DynamoDB. This was limiting because:

1. DynamoDB has a maximum size limit for attributes
2. Large log output couldn't be stored effectively
3. Additional files like charts, CSV data, or other supplementary materials couldn't be attached

To solve this, we've implemented S3 storage for report block details, where:

1. The ReportBlock model includes a `detailsFiles` field that contains a JSON array of file references
2. Each file reference includes a `name` (display name) and `path` (S3 key)
3. Files are stored in the Amplify-managed S3 bucket with a structure of `reportblocks/{report_block_id}/{filename}`

## Backend Components

### S3 Storage Definition

The S3 bucket is defined in Amplify:

```typescript
// dashboard/amplify/storage/resource.ts
export const reportBlockDetails = defineStorage({
  name: 'reportBlockDetails',
  access: (allow) => ({
    'reportblocks/{entity_id}/*': [
      allow.authenticated.to(['read', 'write', 'delete'])
    ],
  })
});
```

### ReportBlock Model

The ReportBlock model includes a `detailsFiles` field:

```typescript
// dashboard/amplify/data/resource.ts
ReportBlock: a
    .model({
        // ... other fields ...
        detailsFiles: a.json(), // JSON array of objects with {name: "display_name", path: "s3_file_path"}
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
1. Include `detailsFiles` in GraphQL queries
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

The `detailsFiles` field contains a JSON array like:

```json
[
  {
    "name": "log.txt",
    "path": "reportblocks/01234567-89ab-cdef-0123-456789abcdef/log.txt"
  },
  {
    "name": "data.csv",
    "path": "reportblocks/01234567-89ab-cdef-0123-456789abcdef/data.csv"
  }
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