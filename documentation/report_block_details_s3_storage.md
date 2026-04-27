# Report Block Details S3 Storage

This document describes how report block artifacts are stored and retrieved in the current reports implementation.

## Overview

Report blocks can produce:

- execution logs (`log.txt`)
- block output payload artifacts (`output-<report_block_id>.json`)
- optional block-specific attachments (CSV, HTML, images, etc.)

These artifacts are stored in S3 to avoid DynamoDB item-size limits and to keep report rendering responsive.

## Storage Model

### `ReportBlock.attachedFiles`

- `attachedFiles` is a list of S3 keys (strings), not file contents.
- In Amplify schema, `ReportBlock.attachedFiles` is `a.string().array()`.
- Typical values look like:

```json
[
  "reportblocks/01234567-89ab-cdef-0123-456789abcdef/log.txt",
  "reportblocks/01234567-89ab-cdef-0123-456789abcdef/output-01234567-89ab-cdef-0123-456789abcdef.json"
]
```

### S3 key format

Artifacts are written under:

`reportblocks/{report_block_id}/{filename}`

The bucket comes from:

1. `AMPLIFY_STORAGE_REPORTBLOCKDETAILS_BUCKET_NAME`
2. default `reportblockdetails-production`

## Backend Write Flow

Primary files:

- `plexus/reports/service.py`
- `plexus/reports/s3_utils.py`

During report generation:

1. A `ReportBlock` record is created.
2. The block runs and returns `output` + `log`.
3. `log.txt` is uploaded to S3 and appended to `attachedFiles`.
4. Output JSON may also be uploaded as `output-<id>.json`.
5. Inline `ReportBlock.output` is compacted to a preview envelope when output is attached.

Compact output envelope example:

```json
{
  "status": "ok",
  "output_compacted": true,
  "preview": {
    "summary": "..."
  },
  "output_attachment": "reportblocks/<block-id>/output-<block-id>.json"
}
```

The compaction behavior is controlled by:

- `REPORT_BLOCK_MAX_INLINE_OUTPUT_CHARS`
- `REPORT_BLOCK_OUTPUT_PREVIEW_CHARS`
- `REPORT_BLOCK_ATTACH_OUTPUT_JSON_ALWAYS`

## Programmatic attachment API

Use `add_file_to_report_block()` in `plexus/reports/s3_utils.py` to append attachments to an existing block.

High-level behavior:

1. Upload file to S3 with `upload_report_block_file()`
2. Load current `ReportBlock`
3. Merge into existing `attachedFiles`
4. Persist with `report_block.update(attachedFiles=file_paths, ...)`

## Frontend Read Flow

Primary file:

- `dashboard/components/blocks/ReportBlock.tsx`

Frontend uses `aws-amplify/storage` APIs:

- `downloadData()` for inline file content
- `getUrl()` for downloadable/viewable URLs

Bucket routing is based on file prefix:

- `reportblocks/*` -> `reportBlockDetails`
- `scoreresults/*` -> `scoreResultAttachments`

## Diagnostics

CLI command:

- `plexus report check-s3`

This validates list/read/write/delete permissions for the report block details bucket.