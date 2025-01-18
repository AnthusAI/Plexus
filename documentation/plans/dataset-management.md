# Dataset Management Plan
*Note: The following sections are required and should be preserved in future updates*

## Background
- Currently using dummy data in the Next.js dashboard for datasets
- Have a working Amplify Gen2 Data Store with Dataset model
- CLI command exists that uses dataset config from score config
- Need to integrate real dataset management via API

## Solution
Create an end-to-end dataset management system that:
1. Stores real dataset configurations in Amplify Data Store
2. Manages them through the Next.js dashboard UI
3. Allows CLI commands to reference datasets by ID
4. Maintains backwards compatibility with existing score config datasets

## Plan
1. Data Store Integration
   - [ ] Add Dataset model to Amplify schema with required fields:
     - id (auto-generated)
     - name
     - description 
     - configuration (JSON)
     - scorecardId (optional)
     - scoreId (optional)
     - createdAt
     - updatedAt
   - [ ] Generate and test Data Store models
   - [ ] Create DatasetService class for CRUD operations

2. Dashboard UI Updates
   - [ ] Update dataset-config-form.tsx to save real configs
   - [ ] Add loading states and error handling
   - [ ] Implement dataset listing with real data
   - [ ] Add dataset deletion capability
   - [ ] Add dataset editing capability

3. CLI Integration  
   - [ ] Add --dataset-id option to evaluation commands
   - [ ] Update dataset loading logic to check for API dataset first
   - [ ] Maintain fallback to score config dataset
   - [ ] Add dataset validation

4. Testing
   - [ ] Unit tests for Dataset model operations
   - [ ] Integration tests for dashboard-API interaction
   - [ ] CLI command tests with dataset override
   - [ ] End-to-end workflow tests

## Current Status
- Have Amplify Data Store setup
- Have dashboard UI mockup working
- Have CLI evaluation command working with score config datasets
- Need to implement real dataset management

## Next Steps
1. Review and validate Dataset model schema
2. Create DatasetService class
3. Update dashboard to use real data
4. Add dataset ID support to CLI

*Note: Update this plan document after each step completed, marking items with ✓ emoji and adding new details learned during implementation.*
