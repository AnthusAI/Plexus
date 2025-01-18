Note: The following sections are required and should be preserved in future edits:
- Background
- Solution
- Plan
- Current Status
- Next Steps

# Landing Page Plan

## Background
We have created several React components for a new landing page (Hero, Layout, Features, CTASection) currently located in `dashboard/components`. These need to be integrated into the Plexus dashboard while keeping them isolated from the existing domain-specific dashboard components. The current home page handles AWS Amplify authentication.

## Solution
Create a dedicated landing page section using Next.js App Router architecture, isolating landing components from the main dashboard components. The landing page will serve as the new entry point at the root route (/), with the current authentication and dashboard functionality moved to a protected `/dashboard` route.

## Plan
1. Organize Landing Page Components
   - ✓ Create `dashboard/components/landing/` directory
   - ✓ Move Hero, Layout, Features, CTASection components there
   - ✓ Update import paths in all components
   - ✓ Verify component isolation from main dashboard

2. Restructure Routes
   - ✓ Move current `page.tsx` (auth handler) to `dashboard/app/dashboard/page.tsx`
   - ✓ Create new landing page at `dashboard/app/page.tsx`
   - Set up layouts:
     - ✓ Root layout remains unchanged
     - ✓ Create dashboard layout for auth-protected routes

3. Authentication Flow
   - ✓ Move AWS Amplify authentication to dashboard route
   - ✓ Update authentication redirects
   - ✓ Add login button routing to dashboard
   - ✓ Fix post-login navigation to activity page
   - ✓ Test unauthenticated and authenticated flows

4. Component Integration
   - Set up proper module paths in tsconfig
   - Update all component imports
   - Verify SSR functionality
   - Test hydration behavior

5. Testing Implementation
   - Add Jest tests for landing components
   - Test authentication flows
   - Add loading states
   - Verify SSR behavior

## Current Status
- Components moved to `dashboard/components/landing/`
- Using Next.js App Router
- Current home page moved to dashboard route
- ✓ New landing page renders correctly at root route
- ✓ Interactive components working as client components
- ✓ Components using system color variables
- ✓ Button styles improved for better contrast and visibility
- ✓ Dashboard layout created with auth protection
- ✓ Login navigation and post-login flow working and tested
- ✓ All layouts configured and working

## Next Steps
1. Add loading states for route transitions
2. Set up proper module paths in tsconfig
3. Add Jest tests for landing components

Note: This plan should be updated after each step is completed to maintain accurate progress tracking and adjust next steps as needed.
