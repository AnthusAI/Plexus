# Account Settings Plan

**Note: The sections below are required and should be preserved through future edits**

## Background
We need to implement account-based menu customization to allow hiding specific menu items based on account settings. This will provide a more tailored dashboard experience for each account.

## Solution
We will:
1. Add a configuration field to the Account model to store account-specific settings ✓
2. Create an account settings UI to manage these configurations ✓
3. Modify the sidebar menu to respect the account's hidden menu items configuration ✓

## Plan
1. Update Account Model Schema ✓
   - Add a `settings` JSON field to the Account model
   - Define a schema for menu configuration that includes `hiddenMenuItems` array
   - Update GraphQL schema and resolvers

2. Create Account Settings UI ✓
   - Create `/settings/account` page
   - Implement settings form with menu item visibility controls
   - Add save/update functionality
   - Add preview of menu with hidden items

3. Update Sidebar Menu Implementation ✓
   - Modify `dashboard-layout.tsx` to fetch account settings
   - Filter menu items based on account's `hiddenMenuItems` setting
   - Add loading state for menu while fetching settings
   - Handle error cases gracefully

4. Testing & Validation ✓
   - Add tests for Account model changes
   - Add tests for settings UI components
   - Add tests for menu filtering logic
   - Manual testing across different accounts

## Current Status
Implementation complete and merged to develop branch:
- Added `settings` JSON field to Account model with validation
- Created TypeScript types for settings with `hiddenMenuItems` array
- Added validation function for settings structure
- Created `/settings/account` page with menu visibility controls
- Implemented settings form with save functionality
- Added loading and error states
- Modified sidebar menu to respect hidden items configuration
- Added comprehensive test coverage
- Successfully tested across multiple accounts
- Feature merged to develop branch with Semantic Release tag

## Future Considerations
1. Performance Monitoring:
   - Monitor performance impact of settings fetching on menu load time
   - Consider caching strategies if needed

2. Feature Extensions:
   - Consider adding more customization options beyond menu visibility
   - Potential for role-based menu customization
   - Possibility to add menu item reordering

3. Maintenance:
   - Keep settings schema in sync with menu items as they evolve
   - Monitor error rates for settings validation
   - Consider adding analytics for most commonly hidden menu items

Note: This feature is now complete and deployed. Future enhancements should be tracked as separate feature requests. 