# Detailed Agent Instructions for Springstack Development

**For project overview and quick start, see [AGENTS.md](AGENTS.md)**

This document contains detailed operational instructions for AI agents working on Springstack feature development, testing, and releases using Beads for issue tracking.

## Development Guidelines

### Code Standards

- **Node version**: 20+ (specified in .nvmrc and package.json)
- **TypeScript**: Strict mode, with type coverage
- **Testing**: Cucumber.js BDD tests (`npm test`)
- **Linting**: ESLint configuration (run via `npm run lint` if available)
- **React**: 18.2.0+, functional components with hooks
- **GSAP**: 3.12.5+ for animations
- **Tailwind CSS**: 3.4.3+ for styling with custom Radix color tokens
- **Documentation**: Update relevant .md files

### File Organization

```
springstack/
├── apps/
│   └── demo/                       # Reference implementation
│       ├── src/
│       │   ├── components/         # React components
│       │   ├── lib/                # Utilities
│       │   └── App.tsx             # Main application
│       └── package.json
├── packages/
│   └── springstack/                # Core library (npm package)
│       ├── src/
│       │   ├── Springstack.tsx     # Main component
│       │   ├── types.ts            # Type definitions
│       │   ├── appearance.ts       # Theme management
│       │   ├── timing.ts           # Animation timing
│       │   ├── typefaces.ts        # Font presets
│       │   ├── ui/                 # UI utilities
│       │   └── useSpringstackController.ts
│       └── package.json
├── infra/                          # AWS CDK deployment
├── features/                       # BDD test specifications
└── *.md                            # Documentation
```

### Testing Workflow

**BDD Tests with Cucumber.js:**

```bash
# Run all tests
npm test

# Run specific feature
npm test -- features/my-feature.feature

# Run with specific tag
npm test -- --tags "@wip"

# Skip tests with @skip tag
npm test  # Automatically skips @skip scenarios
```

**Important Conventions:**
- Test scenarios in `features/*.feature` files
- Step definitions in `features/step_definitions/`
- Support code in `features/support/`
- Use `@skip` tag to temporarily disable scenarios
- Tag scenarios with `@wip` for work-in-progress

### Before Committing

1. **Run tests**: `npm test` (verify all scenarios pass)
2. **Run linting**: `npm run lint` (if available)
3. **Update docs**: If you changed behavior, update README.md or AGENTS.md
4. **Commit**: Issues auto-sync to `.beads/issues.jsonl` and import after pull

### Commit Message Convention

When committing work for an issue, include the issue ID in parentheses at the end:

```bash
git commit -m "Add image file type support component (ss-abc)"
git commit -m "Fix animation timing regression (ss-xyz)"
```

This enables `bd doctor` to detect **orphaned issues** - work that was committed but the issue wasn't closed. The doctor check cross-references open issues against git history to find these orphans.

### Git Workflow

**Auto-sync provides batching!** bd automatically:

- **Exports** to JSONL after CRUD operations (30-second debounce for batching)
- **Imports** from JSONL when it's newer than DB (e.g., after `git pull`)
- **Daemon commits/pushes** every 5 seconds (if `--auto-commit` / `--auto-push` enabled)

The 30-second debounce provides a **transaction window** for batch operations - multiple issue changes within 30 seconds get flushed together, avoiding commit spam.

### Git Integration

**Auto-sync**: bd automatically exports to JSONL (30s debounce), imports after `git pull`, and optionally commits/pushes.

**Protected branches**: Use `bd init --branch beads-metadata` to commit to separate branch. See `.beads/README.md` for details.

**Merge conflicts**: Rare with hash IDs. If conflicts occur, use `git checkout --theirs/.beads/issues.jsonl` and `bd import`.

## Landing the Plane

**When the user says "let's land the plane"**, you MUST complete ALL steps below. The plane is NOT landed until `git push` succeeds. NEVER stop before pushing. NEVER say "ready to push when you are!" - that is a FAILURE.

**MANDATORY WORKFLOW - COMPLETE ALL STEPS:**

1. **File beads issues for any remaining work** that needs follow-up
2. **Ensure all quality gates pass** (only if code changes were made):
   - Run `npm test` (verify all BDD tests pass)
   - Run `npm run lint` if available
   - File P0 issues if quality gates are broken
3. **Update beads issues** - close finished work, update status
4. **PUSH TO REMOTE - NON-NEGOTIABLE** - This step is MANDATORY. Execute ALL commands below:
   ```bash
   # Pull first to catch any remote changes
   git pull --rebase

   # If conflicts in .beads/issues.jsonl, resolve thoughtfully:
   #   - git checkout --theirs .beads/issues.jsonl (accept remote)
   #   - bd import -i .beads/issues.jsonl (re-import)
   #   - Or manual merge, then import

   # Sync the database (exports to JSONL, commits)
   bd sync

   # MANDATORY: Push everything to remote
   # DO NOT STOP BEFORE THIS COMMAND COMPLETES
   git push

   # MANDATORY: Verify push succeeded
   git status  # MUST show "up to date with origin/main"
   ```

   **CRITICAL RULES:**
   - The plane has NOT landed until `git push` completes successfully
   - NEVER stop before `git push` - that leaves work stranded locally
   - NEVER say "ready to push when you are!" - YOU must push, not the user
   - If `git push` fails, resolve the issue and retry until it succeeds
   - The user is managing multiple agents - unpushed work breaks their coordination workflow

5. **Clean up git state** - Clear old stashes and prune dead remote branches:
   ```bash
   git stash clear                    # Remove old stashes
   git remote prune origin            # Clean up deleted remote branches
   ```
6. **Verify clean state** - Ensure all changes are committed AND PUSHED, no untracked files remain
7. **Choose a follow-up issue for next session**
   - Provide a prompt for the user to give to you in the next session
   - Format: "Continue work on ss-X: [issue title]. [Brief context about what's been done and what's next]"

**REMEMBER: Landing the plane means EVERYTHING is pushed to remote. No exceptions. No "ready when you are". PUSH IT.**

## Agent Session Workflow

**WARNING: DO NOT use `bd edit`** - it opens an interactive editor ($EDITOR) which AI agents cannot use. Use `bd update` with flags instead:
```bash
bd update <id> --description "new description"
bd update <id> --title "new title"
bd update <id> --design "design notes"
bd update <id> --notes "additional notes"
bd update <id> --acceptance "acceptance criteria"
```

**IMPORTANT for AI agents:** When you finish making issue changes, always run:

```bash
bd sync
```

This immediately:

1. Exports pending changes to JSONL (no 30s wait)
2. Commits to git
3. Pulls from remote
4. Imports any updates
5. Pushes to remote

**Example agent session:**

```bash
# Make multiple changes (batched in 30-second window)
bd create "Add video file type support" -p 2
bd create "Add audio file type support" -p 2
bd update ss-42 --status in_progress
bd close ss-40 --reason "Completed"

# Force immediate sync at end of session
bd sync

# Now safe to end session - everything is committed and pushed
```

**Why this matters:**

- Without `bd sync`, changes sit in 30-second debounce window
- User might think you pushed but JSONL is still dirty
- `bd sync` forces immediate flush/commit/push

**STRONGLY RECOMMENDED: Install git hooks for automatic sync** (prevents stale JSONL problems):

```bash
# One-time setup - run this in the springstack workspace
bd hooks install
```

This installs:

- **pre-commit** - Flushes pending changes immediately before commit (bypasses 30s debounce)
- **post-merge** - Imports updated JSONL after pull/merge (guaranteed sync)
- **pre-push** - Exports database to JSONL before push (prevents stale JSONL from reaching remote)
- **post-checkout** - Imports JSONL after branch checkout (ensures consistency)

**Why git hooks matter:**
Without the pre-push hook, you can have database changes committed locally but stale JSONL pushed to remote, causing multi-workspace divergence. The hooks guarantee DB ↔ JSONL consistency.

## Common Development Tasks

### Adding File Type Support

When adding support for a new file type (e.g., video, audio, PDF):

1. **Define file type characteristics** in a bead including:
   - Icon to use (from lucide-react)
   - Content view component structure (React TSX example)
   - List card metadata display format
   - Breadcrumb appearance
   - MIME types this covers

2. **Implement renderer** in demo or library:
   - Add list slot renderer with icon
   - Add crumb slot renderer
   - Add panel slot renderer for detail view
   - Include file-type-specific metadata in metaLine

3. **Test in demo app**:
   - Add test nodes with the new file type
   - Verify morphing and animations work
   - Test metadata display on cards and breadcrumbs

4. **Update documentation** (README.md or this file) with examples

### Development Workflow

```bash
# Install dependencies
npm install

# Development server for demo app
npm run dev --workspace apps/demo

# Build library for npm
npm run build --workspace packages/springstack

# Run tests
npm test

# Build demo for deployment
npm run build --workspace apps/demo

# Deploy to AWS (requires AWS credentials)
npm run cdk:deploy --workspace infra -- --require-approval never
```

### Styling and Theme Integration

- **Icon library**: lucide-react with `strokeWidth={2.25}`
- **Colors**: Radix UI tokens (--primary, --secondary, --muted, --card, --selected, etc.)
- **Spacing**: Standard gap-2 (0.5rem) between elements
- **Padding**: Standard p-2 (0.5rem) for cards and regions
- **Rounded corners**: rounded-md (0.375rem) for consistency
- **Tailwind utilities**: Use dark mode with `dark:` prefix

## Testing

```bash
# Run all BDD tests
npm test

# Run with output
npm test -- --format @cucumber/pretty-formatter

# Run specific feature
npm test -- features/file-types.feature

# List available scenarios
npm test -- --dry-run
```

## Release

- Releases are handled by GitHub Actions using **semantic-release**
- Uses **conventional commits** for versioning (fix: patch, feat: minor, BREAKING CHANGE: major)
- CI runs `npm test` and then publishes `springstack` if tests pass
- Requires `NPM_TOKEN` secret in GitHub Actions

Commit guidelines:
- `feat:` - New features (triggers minor version bump)
- `fix:` - Bug fixes (triggers patch version bump)
- `BREAKING CHANGE:` in body - Major version bump
- `docs:` - Documentation only (no version bump)
- `test:` - Test updates (no version bump)

## Questions?

- Check existing issues: `bd list`
- Look at recent commits: `git log --oneline -20`
- Read the docs: README.md, AGENTS.md
- Create an issue if unsure: `bd create "Question: ..." -t task -p 2`

## Important Files

- **README.md** - Main documentation and project overview
- **AGENTS.md** - Quick start and architecture overview
- **packages/springstack/src/types.ts** - Type definitions and renderer interfaces
- **apps/demo/src/components/demos/SpringstackDemo.tsx** - Reference implementation
- **apps/demo/src/App.tsx** - Main demo application structure
