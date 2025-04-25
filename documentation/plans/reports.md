# Plexus Reports Feature Plan

**Status Legend:**
*   ⬜ Not Started / To Do
*   🟡 In Progress
*   ✅ Completed

## Introduction

This document outlines the plan for implementing a flexible and extensible reporting system within the Plexus platform. The goal is to provide a standardized way to define, generate, store, and view various types of reports and analyses without requiring bespoke dashboard pages or API schema changes for each new report type. This system will support reports like feedback analysis, topic modeling, score performance summaries, and more.

## Core Concepts

The reporting system will be built around three core concepts:

*   **`ReportConfiguration`**: Defines the structure, content sources, and parameters for a specific type of report. It acts as a template for generating reports.
*   **`Report`**: Represents a specific instance of a report generated based on a `ReportConfiguration` at a particular point in time. It stores the actual generated data and metadata about the run.
*   **`ReportBlock` (Python Class)**: Reusable Python components responsible for generating specific sections or data points within a report. These blocks encapsulate the logic for fetching data (e.g., from evaluations, scores, external sources) and performing necessary analysis or aggregation.

## Data Models

### `ReportConfiguration`

*   **Storage:** Stored as Markdown text within a database model (e.g., `ReportConfiguration`). This allows for embedding rich text, headers, and other Markdown elements alongside the block configurations.
*   **Structure:**
    *   `name`: Human-readable name for the configuration.
    *   `description`: Optional description.
    *   `accountId`: Link to the owning account.
    *   `configuration`: The core Markdown definition. This content will be rendered directly, with specific sections interpreted as Report Blocks:
        *   **Embedded Blocks:** Report Blocks are defined using fenced code blocks with the `block` language identifier (e.g., ````block```). The content inside these blocks will be parsed as YAML, specifying the `pythonClass` to use and its parameters (e.g., `scorecardId`, `timeRange`).
        *   **Markdown Content:** Any standard Markdown content (headers, paragraphs, lists, images) outside the ````block` fences will be treated as static content for the report layout.
    *   Standard metadata (`createdAt`, `updatedAt`, etc.).

### `Report`

*   **Storage:** A new database model (`Report`) linked to a `ReportConfiguration`.
*   **Structure:**
    *   `reportConfigurationId`: Link to the configuration used.
    *   `accountId`: Link to the owning account.
    *   `name`: Can be auto-generated or user-defined.
    *   `status`: (e.g., `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`).
    *   `createdAt`, `startedAt`, `completedAt`: Timestamps for the run.
    *   `parameters`: Parameters used for this specific run (might override or supplement configuration).
    *   `reportData`: The generated report output, stored as JSON. This data structure will be determined by the blocks used in the configuration.
    *   `errorMessage`, `errorDetails`: For tracking failures.
    *   `shareLinks`: Association for shareable URLs.

## Backend Implementation

### Python `ReportBlock` Framework

*   Define a base Python class (e.g., `plexus.reports.blocks.BaseReportBlock`).
*   Subclasses will implement specific report generation logic (e.g., `FeedbackAnalysisBlock`, `TopicModelBlock`, `ScorePerformanceBlock`).
*   Blocks will implement a standard method (e.g., `generate(config, params)`) that returns a JSON-serializable dictionary.
*   Blocks should have access to Plexus data fetching utilities (e.g., to query `Score`, `Evaluation`, `Item` data via the API or direct DB access if necessary).

### Report Generation Service

*   A mechanism to trigger report generation based on a `ReportConfiguration`.
*   Options:
    *   **CLI Command:** `plexus report run --config <config_id_or_name> [params...]`
    *   **Celery Task:** Dispatch report generation jobs to worker nodes, similar to evaluations. This is suitable for long-running reports.
*   The service will:
    1.  Load the `ReportConfiguration`.
    2.  Parse the Markdown `configuration` content.
    3.  Identify and extract YAML content from ```block``` sections.
    4.  Instantiate and execute the specified `ReportBlock`s based on the parsed YAML, passing the parameters.
    5.  Assemble the results from the blocks (along with potentially rendering the static Markdown content) into the final `reportData` JSON.
    6.  Create/Update the `Report` database record with the status and results.

## Frontend Implementation (Dashboard)

### Management Interface

*   New dashboard section for "Reports".
*   View/List existing `ReportConfiguration`s and `Report`s.
*   Create/Edit `ReportConfiguration`s:
    *   Use a Markdown editor (like `react-markdown` or a dedicated component) to edit the `configuration` field.
    *   A more user-friendly UI builder that abstracts the Markdown/YAML could be a future enhancement.
*   Trigger new `Report` runs from a configuration.

### Report Viewing

*   Dedicated page or component to display a `Report`.
*   Fetch the `Report` record, including its `reportData` JSON.
*   Dynamically render the `reportData` using React components.
    *   Develop a library of standard React components corresponding to different data structures potentially generated by `ReportBlock`s (e.g., tables, charts, key metrics, text sections).
    *   The rendering logic will interpret the `reportData` JSON structure to select appropriate components.
*   **Sharing:** Integrate with the existing `ShareLink` system to allow sharing report URLs.
*   **Printing:** Implement CSS media queries (`@media print`) to provide a clean, printable version of the report view, removing UI chrome.

## Implementation Plan & Checklist

*   ✅ **Define Models:** Define `ReportConfiguration` and `Report` models in `dashboard/amplify/data/resource.ts`.
    *   ✅ Add fields for `ReportConfiguration` (name, description, accountId, configuration (string), createdAt, updatedAt).
    *   ✅ Add fields for `Report` (reportConfigurationId, accountId, name, status, createdAt, startedAt, completedAt, parameters (json), reportData (json), errorMessage, errorDetails).
*   ✅ **Define Relationships:** Add necessary relationships (e.g., `Account` -> `ReportConfiguration`, `ReportConfiguration` -> `Report`, `Account` -> `Report`). Consider if links to `Scorecard`, `Score` etc. are needed directly on `ReportConfiguration` or `Report` or if they should solely be defined within the `configuration`/`parameters` JSON.
*   ✅ **Add Indexes:** Define required secondary indexes for efficient querying (e.g., by `accountId`, `reportConfigurationId`, `status`).

### Phase 1: Backend Foundation (Post-Schema)

*   ✅ **Update Models:** Adjust the `ReportConfiguration` model in `dashboard/amplify/data/resource.ts` to store `configuration` as a `string` (or appropriate large text type) instead of JSON. Re-run `amplify generate models`.
*   ✅ **Create Base Python Class:** Create the base `plexus.reports.blocks.BaseReportBlock` Python class with a placeholder `generate` method. 

### Phase 2: Report Generation (Service & Triggering)

*   ✅ **Implement Initial Block:** Implement a simple `ScoreInfoBlock` in Python. This block will take a `scoreId` and optional parameters (e.g., `include_variant`) and return mock JSON data representing basic information about that score.
*   ✅ **Develop Generation Service Core:** Create Python service logic (`plexus.reports.service`) that:
    *   ✅ Takes a `ReportConfiguration` ID and optional parameters.
    *   ✅ Loads the `ReportConfiguration` data (initially mocked or via basic GraphQL query).
    *   ✅ Parses the Markdown `configuration` field, extracting YAML from ```block``` sections (using libraries like `mistune` or `markdown-it` and `PyYAML`).
    *   ✅ Identifies `ReportBlock`s based on the extracted YAML (initially just handle the `ScoreInfoBlock`).
    *   ✅ Instantiates and calls the `generate` method for identified blocks.
    *   ✅ Assembles the results into a final `reportData` JSON.
*   ⬜ **Implement CLI Trigger:** Create the `plexus report run --config <config_id>` CLI command that:
    *   ⬜ Parses arguments.
    *   ⬜ Calls the generation service logic.
    *   ⬜ Creates/Updates the `Report` record via GraphQL mutation (initially just setting `status` to `PENDING`, then `COMPLETED`/`FAILED` and storing `reportData`).
*   ⬜ **Add Unit Tests:** Implement unit tests for `plexus.reports.service` and `plexus.reports.blocks` (covering parsing, block execution, error handling, etc.).
*   ⬜ **Basic Status Updates:** Ensure the `Report` record `status`, `startedAt`, `completedAt`, `errorMessage`, `reportData` are updated correctly by the CLI process.
*   ⬜ **Implement Celery Task:** Wrap the generation service logic in a Celery task.
*   ⬜ **Implement Celery Dispatch:** Create a mechanism (e.g., internal API call, GraphQL mutation triggered by frontend) to dispatch the Celery task for report generation.
*   ⬜ **Add Error Handling:** Implement robust error handling in the generation service and Celery task to capture exceptions and update the `Report` record with `errorMessage` and `errorDetails`.
*   ⬜ **Verify Phase 2:** Confirm reports can be generated via CLI, data is stored, status updates correctly. Test Celery task dispatch and execution.

### Phase 3: Frontend Basics (Management & Display)

*   ⬜ **Create "Reports" Dashboard Section:** Add a new top-level section/route (e.g., `/reports`) in the Next.js dashboard.
*   ⬜ **List Configurations:** Implement a UI table/list to display existing `ReportConfiguration`s fetched via GraphQL.
*   ⬜ **List Reports:** Implement a UI table/list to display existing `Report`s fetched via GraphQL, showing key metadata (name, status, created date).
*   ⬜ **Basic Configuration Editor:** Create a simple form/modal to create/edit `ReportConfiguration`s (editing name, description, and the raw `configuration` Markdown for now). Use GraphQL mutations.
*   ⬜ **Trigger Generation from UI:** Add a button on the `ReportConfiguration` list/view to trigger a new report run (using the Celery dispatch mechanism from Phase 2).
*   ⬜ **Basic Report View:** Create a dedicated route/page (e.g., `/reports/[reportId]`) to display a single `Report`.
*   ⬜ **Fetch Report Data:** Implement logic on the report view page to fetch the full `Report` record, including the `reportData` JSON.
*   ⬜ **Initial Dynamic Rendering:** Develop basic React components to render simple structures found in `reportData` (e.g., display key-value pairs, render paragraphs of text based on the `ScoreInfoBlock` output).
*   ⬜ **Verify Phase 3:** Confirm basic UI for listing, creating configurations, triggering runs, and viewing simple reports works.

### Phase 4: Advanced Features & Polish

*   ⬜ **Implement Core Report Blocks:**
    *   ⬜ Implement `FeedbackAnalysisBlock`.
    *   ⬜ Implement `ScorePerformanceBlock`.
    *   ⬜ Implement `TopicModelBlock` (if applicable).
*   ⬜ **Develop Corresponding React Components:** Create specific React components to visualize the data generated by the new blocks (e.g., charts for performance, tables for feedback, topic lists).
*   ⬜ **Enhance Dynamic Rendering:** Improve the report viewing component to intelligently select and render the appropriate React component based on the structure/type information within the `reportData` JSON.
*   ⬜ **Integrate Sharing:** Connect the `Report`