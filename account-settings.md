# Account Settings Plan

**Note: The sections below are required and should be preserved through future edits**

## Background
We need to implement account-based menu customization to allow hiding specific menu items based on account settings. This will provide a more tailored dashboard experience for each account.

## Solution
We will:
1. Add a configuration field to the Account model to store account-specific settings
2. Create an account settings UI to manage these configurations
3. Modify the sidebar menu to respect the account's hidden menu items configuration

## Plan
1. Update Account Model Schema
   - Add a `configuration` JSON field to the Account model
   - Define a schema for menu configuration that includes `hiddenMenuItems` array
   - Update GraphQL schema and resolvers
   - Add migration for existing accounts

2. Create Account Settings UI
   - Create `/settings/account` page
   - Implement settings form with menu item visibility controls
   - Add save/update functionality
   - Add preview of menu with hidden items

3. Update Sidebar Menu Implementation
   - Modify `dashboard-layout.tsx` to fetch account configuration
   - Filter menu items based on account's `hiddenMenuItems` setting
   - Add loading state for menu while fetching configuration
   - Handle error cases gracefully

4. Testing & Validation
   - Add tests for Account model changes
   - Add tests for settings UI components
   - Add tests for menu filtering logic
   - Manual testing across different accounts

## Current Status
Schema update in progress:
- Added `configuration` JSON field to Account model
- Deployment of schema changes in progress

## Next Steps
1. After schema deployment completes:
   - Define configuration JSON schema structure for menu settings
   - Update GraphQL schema if needed
   - Create migration plan for existing accounts

Note: This plan should be updated after each step is completed to reflect current status and adjust next steps as needed. 