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
   - [✓] Add base Dataset model
   - [✓] Add DatasetVersion model
   - [✓] Add DatasetProfile model
   - [✓] Define relationships between models
   - [ ] Write unit tests for model relationships
      - Test Dataset-DatasetVersion relationships
      - Test Dataset-DatasetProfile relationships
      - Test DatasetVersion-DatasetProfile relationships
      - Test currentVersion relationship logic

2. Dashboard Service Layer
   - [ ] Create DatasetService class with CRUD operations
      - Create dataset with initial version
      - Update dataset metadata
      - List datasets with current versions
      - Delete dataset and all versions
   - [ ] Add version management methods
      - Create new version
      - Update version configuration
      - List versions for dataset
      - Compare versions
   - [ ] Add profile management methods
      - Create profile for version
      - List profiles for dataset/version
      - Generate profile metrics
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
- [✓] Have Amplify Gen2 Data Store models defined and deployed
- Have dashboard UI mockup working
- Have CLI evaluation command working with score config datasets
- Need to implement service layer and UI integration

## Next Steps
1. Create test suite for model relationships
2. Design and implement DatasetService interface
3. Implement core CRUD operations in service layer
4. Write service layer unit tests
5. Begin UI integration with service layer

*Note: This plan should be updated after each step is completed, marking items with ✓ emoji and adding new details learned during implementation. Each step should be verified through tests before proceeding.*
