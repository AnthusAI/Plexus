# Dataset Management Plan
*Note: The following sections are required and should be preserved in future updates*

## Background
- Currently using dummy data in the Next.js dashboard for datasets
- Have a working Amplify Gen2 Data Store with Dataset model
- CLI command exists that uses dataset config from score config
- Need to integrate real dataset management via API
- Need versioning of dataset configurations
- Need profiling of dataset instances
- Need to track relationships between datasets, versions, and profiles

## Solution
Create an end-to-end dataset management system that:
1. Stores real dataset configurations in Amplify Data Store with versioning
2. Tracks dataset profiles separately from versions
3. Manages them through the Next.js dashboard UI
4. Allows CLI commands to reference datasets by ID
5. Maintains backwards compatibility with existing score config datasets

## Plan
1. Data Store Schema Updates
   - [ ] Add base Dataset model:
     ```graphql
     type Dataset @model {
       id: ID!
       name: String!
       description: String
       scorecardId: ID
       scoreId: ID
       currentVersionId: ID
       currentVersion: DatasetVersion @belongsTo
       versions: [DatasetVersion] @hasMany
       profiles: [DatasetProfile] @hasMany
       createdAt: AWSDateTime!
       updatedAt: AWSDateTime!
     }
     ```
   - [ ] Add DatasetVersion model:
     ```graphql
     type DatasetVersion @model {
       id: ID!
       datasetId: ID!
       dataset: Dataset @belongsTo
       versionNumber: Int!
       configuration: AWSJSON!
       createdAt: AWSDateTime!
       profiles: [DatasetProfile] @hasMany
     }
     ```
   - [ ] Add DatasetProfile model:
     ```graphql
     type DatasetProfile @model {
       id: ID!
       datasetId: ID!
       dataset: Dataset @belongsTo
       datasetVersionId: ID!
       datasetVersion: DatasetVersion @belongsTo
       queryResults: AWSJSON!
       filteredResults: AWSJSON!
       columnList: [String]!
       recordCounts: AWSJSON!
       answerDistribution: AWSJSON!
       createdAt: AWSDateTime!
     }
     ```
   - [ ] Generate and test Data Store models
   - [ ] Write unit tests for model relationships

2. Dashboard Service Layer
   - [ ] Create DatasetService class with CRUD operations
   - [ ] Add version management methods
   - [ ] Add profile management methods
   - [ ] Write unit tests for service layer

3. Dashboard UI Updates (Iterative)
   - [ ] Update dataset listing to use real data
   - [ ] Add dataset creation form
   - [ ] Add version management UI
   - [ ] Add profile viewing UI
   - [ ] Add version comparison view
   - [ ] Add profile history view
   - [ ] Write component tests

4. CLI Integration
   - [ ] Add --dataset-id option to evaluation commands
   - [ ] Add version resolution logic
   - [ ] Add profile recording logic
   - [ ] Write CLI integration tests

## Current Status
- Have Amplify Data Store setup
- Have dashboard UI mockup working
- Have CLI evaluation command working with score config datasets
- Need to implement real dataset management with versioning and profiling

## Next Steps
1. Review and validate expanded data model schema
2. Set up test infrastructure for TDD approach
3. Start with base Dataset model implementation
4. Add version management
5. Add profile tracking

*Note: This plan should be updated after each step is completed, marking items with ✓ emoji and adding new details learned during implementation. Each step should be verified through tests before proceeding.*
