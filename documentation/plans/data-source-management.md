# Data Source & Dataset Management

This document outlines the plan for improving data source and dataset management within Plexus, including support for data versioning and previewing of Parquet files.

## Problem

While the foundational data models (`DataSource`, `DataSet`) exist, Plexus currently lacks the UI and backend logic to effectively manage them. This leads to several challenges:

*   **No UI for Management:** There is no interface for users to create, view, update, or manage their data sources and datasets.
*   **Inefficient Data Handling:** The platform is not yet equipped to handle modern data formats like Apache Parquet efficiently, which is a standard for large-scale data.
*   **No Previewing:** Users cannot inspect the contents of their data sources directly within the platform. They have to download files and use external tools, which is inefficient and cumbersome.

## Solution

We will build a comprehensive UI and the supporting backend logic for the existing `DataSource` and `DataSet` models. We will also leverage modern, browser-native libraries for efficient data handling and previewing.

The core components of the solution are:

1.  **Backend Logic:** Implement the business logic for creating and versioning `DataSource` and `DataSet` records. This includes handling file uploads and linking them to the correct data models.
2.  **Parquet File Previews:** Integrate `@hyparquet`, a lightweight and performant in-browser Parquet parser. This will allow users to instantly preview the contents of `.parquet` files directly in the dashboard without needing to download them or rely on server-side processing.
3.  **UI for Management:** Develop new UI components in the dashboard for:
    *   Creating, viewing, and managing `DataSource` entities.
    *   Uploading data files (like `.parquet` or `.csv`) that create and version `DataSource` records.
    *   Viewing the version history of a `DataSource` via `DataSourceVersion` records.
    *   Displaying generated `DataSet` files.
    *   A powerful Parquet file previewer.

## Action Items

Here is the step-by-step plan to implement the solution.

### Legend

*   ⚪️ Not Started
*   🟡 In Progress
*   🟢 Done
*   ⚫️ Blocked

### Phase 1: Backend & Data Modeling

*   [🟢] **Define `DataSource` and `Dataset` Models:** The `DataSource`, `DataSourceVersion`, and `DataSet` models are already defined in `dashboard/amplify/data/resource.ts`.
*   [🟢] **Implement File Upload Logic:** The core `onUpload` handler is implemented in `DataSourceComponent.tsx`, which correctly uploads files to S3 and updates the `DataSource` record.

### Phase 2: UI Implementation & Refinement

*   [🟢] **`DataSource` List & Detail Views:** A sophisticated multi-panel UI for managing data sources and datasets already exists in `dashboard/components/data-sources-dashboard.tsx`.
*   [🟢] **File Upload Component:** The reusable `FileAttachments` component is fully integrated into the `DataSourceComponent` and is operational.

### Phase 3: Parquet Preview Integration

*   [⚪️] **Create Test Data Generator:** Develop a CLI script in a client project to generate a sample `.parquet` file for testing the viewer.
*   [🟢] **Install `hyparquet`:** Added `hyparquet` and `hyparquet-compressors` to the dashboard's `package.json`.
*   [🟢] **Create Parquet Viewer Component:** Developed a React component (`ParquetViewer.tsx`) that takes a file URL and uses `hyparquet` to render a preview of the data.
*   [🟢] **Integrate Viewer:** Enhanced the `FileAttachments` component with view functionality for Parquet files and other text-based files, integrated into the data source dashboard.
*   [🟢] **Dataset Parquet Preview:** Added automatic Parquet file preview to the `DataSetComponent` detail view, taking up the full available space when a Parquet file is present.

### Phase 4: Versioning Logic & Finalization

*   [⚪️] **Versioning Logic:** Implement the business logic for creating and managing `DataSourceVersion` records when a `DataSource` is updated.
*   [⚪️] **End-to-End Testing:** Thoroughly test the entire workflow from data source creation and uploading to versioning and previewing.
*   [⚪️] **Documentation:** Update the user documentation to cover the new data source management features.

### Phase 5: Dataset Generation

*   [⚪️] **Create `plexus dataset load` command:** Implement a CLI command that takes a `DataSource` name, loads the corresponding data using its `yamlConfiguration`, generates a `.parquet` file, and attaches it to a new `DataSet` record.

## Existing Context & Roadmap

This section provides context on the existing implementation to guide future development.

### File Upload Workflow

The file upload functionality is already implemented and works as follows:

1.  **UI Component (`FileAttachments.tsx`):**
    *   The primary UI is handled by the reusable React component located at `dashboard/components/items/FileAttachments.tsx`.
    *   This component manages the state for a list of file paths, displaying them to the user.
    *   It accepts an `onUpload` function as a prop, which it calls when a user selects a file to upload. It then displays the upload progress and either the returned file path or an error message.

2.  **Dashboard UI (`data-sources-dashboard.tsx`):**
    *   The main dashboard for this feature is `dashboard/components/data-sources-dashboard.tsx`.
    *   It features a multi-panel layout for listing `DataSources` and displaying the detail view (`DataSourceComponent`).
    *   It handles fetching data, selecting data sources, and orchestrating CRUD operations (Create, Read, Update, Delete).

3.  **Integration (`DataSourceComponent.tsx`):**
    *   The `FileAttachments` component is integrated into `dashboard/components/data-sources/DataSourceComponent.tsx`.
    *   It uses `uploadData` from `aws-amplify/storage` to upload the file to Amazon S3.
    *   Files are stored with a structured path: `datasources/{accountId}/{dataSourceId}/{timestamp}-{fileName}`.
    *   After a successful upload, it calls `amplifyClient.DataSource.update` to persist the new file path in the `attachedFiles` array of the corresponding `DataSource` record in the database.

### Development Roadmap

Based on this existing context, the next logical steps from the action items are:

1.  **Implement Parquet Preview:** This is the highest priority. Create the `ParquetViewer` component and integrate it into the `DataSourceComponent` detail view to preview files stored in `attachedFiles`.
2.  **Implement Versioning Logic:** Once the core UI is complete and previews are working, implement the versioning logic as described below.
3.  **Finalize and Document:** Complete end-to-end testing and write user documentation.

## Versioning Logic Explained

The versioning system is core to maintaining a traceable and reproducible history for each data source. The `DataSource` model represents the "live" or "current" configuration, while the `DataSourceVersion` model creates an immutable, historical record of the data source at a specific point in time.

### How it Should Work

1.  **User Action as Trigger:** The creation of a new version should be triggered by a direct user action, specifically when they click a "Save" or "Update" button after making changes to a `DataSource` (e.g., editing its YAML configuration or changing attached files).

2.  **The `onSave` Workflow:** The primary logic should reside within the `onSave` handler in `DataSourceComponent.tsx`. When called, it will execute the following steps:
    *   **Create `DataSourceVersion`:** A new `DataSourceVersion` record is created in the database.
    *   **Snapshot Data:** It captures a snapshot of the `DataSource`'s state at that moment. This includes copying the `yamlConfiguration`, the list of `attachedFiles`, and any other relevant fields into the new `DataSourceVersion` record.
    *   **Set Version Number:** The `versionNumber` is calculated, typically by finding the previous version's number and incrementing it. For the first version, it would be `1`.
    *   **Maintain History:** The new version is linked to the previous one via the `parentVersionId` field, creating a clear, unbroken chain of changes.
    *   **Update the "Live" Record:** After the historical version is successfully saved, the main `DataSource` record is updated. Crucially, its `currentVersionId` field is set to the ID of the newly created `DataSourceVersion`.

### Data Loading Mechanism

The data loading process for evaluations and dataset generation is driven by the `data` configuration block within a score's or `DataSource`'s YAML configuration. This design allows for a flexible, pluggable architecture for sourcing data.

1.  **`DataCache` Abstract Class:** The core abstraction is `plexus.data.DataCache`, which defines the interface for all data loading classes. The key method is `load_dataframe`, which is responsible for fetching data and returning it as a pandas DataFrame.

2.  **`CallCriteriaDBCache` Implementation:**
    *   The primary implementation used in this project is `plexus_extensions.CallCriteriaDBCache.CallCriteriaDBCache`, located in the `Call-Criteria-Python` client project.
    *   This class is designed to connect to the Call-Criteria MS SQL Server database.
    *   It uses the `searches` and `queries` sections of the `data` configuration to fetch specific sets of call review forms (`f_id`s) and their associated data.
    *   It includes a sophisticated local caching mechanism to store both the generated dataframes (`.parquet` files) and individual content items (metadata and transcripts) to speed up subsequent runs. The `fresh=True` flag can be used to bypass this cache.

3.  **Dynamic Loading:** The system dynamically imports and instantiates the `DataCache` class specified in the YAML configuration. This is handled by the `plexus dataset load` command and the `EvaluationCommands.py` script, allowing different data sources to use different loading logic without code changes.

### Example Flow

*   A user edits the YAML config of "My First Data Source".
*   They click "Save".
*   The `onSave` function fires.
*   A new `DataSourceVersion` (version #2) is created with the new YAML. Its `parentVersionId` points to version #1.
*   The `DataSource` record for "My First Data-Source" has its `currentVersionId` updated to point to the new version #2 record.
*   The UI refreshes, now showing the data source as of version 2, but the full history is preserved in the database.
