# Plexus Dashboard Guide

## Build Commands
- Development: `npm run dev`
- Build: `npm run build`
- Start (prod): `npm run start`
- Lint: `npm run lint`
- Typecheck: `npm run typecheck`

## Test Commands
- Run all tests: `npm test`
- Watch mode: `npm run test:watch`
- Test coverage: `npm run test:coverage`
- Run single test: `npx jest path/to/test.test.tsx`
- Storybook: `npm run storybook`
- Test storybook: `npm run test:storybook`

## CI Commands (mirrors production pipeline)
- Run full CI pipeline: `npm run ci`
- Type checking only: `npm run ci:typecheck`
- Unit tests with coverage: `npm run ci:unit`
- Storybook tests: `npm run ci:storybook`

## Code Style Guidelines
- Use TypeScript with strict type checking
- Follow Next.js conventions for file/folder structure
- Import order: React � external libraries � internal modules
- Use absolute imports with `@/` prefix
- Prefer functional components with hooks over class components
- Use shadcn UI components from `/components/ui/`
- Error handling: use try/catch blocks and proper error messaging
- File naming: kebab-case for files, PascalCase for components
- Component props interfaces should be defined with `{ComponentName}Props`
- Use tailwind for styling with responsive design in mind