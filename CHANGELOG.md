# CHANGELOG


## v0.3.0 (2025-01-02)


## v0.3.0-rc.1 (2025-01-02)

### Continuous Integration

- Added Storybook interaction tests to `npm run ci`. Added new tests.
  ([`db24008`](https://github.com/AnthusAI/Plexus/commit/db240089f81d33f8978e105762db39283f9d8760))


## v0.2.0-alpha.3 (2025-01-01)

### Features

- **dashboard**: Increase precision when accuracy is near 100%. "99.4%" instead of rounding to
  "100%".
  ([`ab874c2`](https://github.com/AnthusAI/Plexus/commit/ab874c2d721e04e540eaaa332d774253a22d59e0))

- **dashboard**: Increase precision when accuracy is near 100%. resolves #18
  ([`09e2233`](https://github.com/AnthusAI/Plexus/commit/09e223315e0c4bc810a8df20f2a2bfbb7b1f8215))


## v0.2.0 (2025-01-01)


## v0.2.0-rc.1 (2025-01-01)


## v0.2.0-alpha.2 (2024-12-31)

### Features

- **dependencies**: Add conditional dependencies and primary score filtering
  ([`27d0d34`](https://github.com/AnthusAI/Plexus/commit/27d0d34db2d878683d1ec12e6a34e12ba69b2c7a))

- Add support for conditional dependencies in score configurations - Filter metrics and dashboard
  reporting to only include primary score - Skip processing of dependency scores in evaluation
  results - Support both simple list and dictionary formats for dependencies - Add validation for
  dependency conditions before score execution


## v0.2.0-alpha.1 (2024-12-31)

### Features

- **python**: Moved from setup.py to pyproject.toml
  ([`50bdc88`](https://github.com/AnthusAI/Plexus/commit/50bdc888254ce84f3aa87add22cb4fa20215906f))


## v0.1.0 (2024-12-31)


## v0.0.0 (2024-12-31)

### Bug Fixes

- Improve confusion matrix generation and prediction tracking
  ([`46f8d08`](https://github.com/AnthusAI/Plexus/commit/46f8d08af850e820c85e227648bb86986ebc830e))

- Fix confusion matrix generation with proper label ordering and value counts - Add score name to
  distribution entries for better tracking - Improve value standardization for predictions and
  actual labels - Add detailed logging for confusion matrices and distributions - Fix empty/NA value
  handling to be more consistent - Add percentage calculations to distribution metrics

- **build**: Batchjobtask stuff.
  ([`df2caa8`](https://github.com/AnthusAI/Plexus/commit/df2caa87f70355a7da533e1b03d2d890a1d3debb))

### Chores

- Add storybook-static/ to .gitignore
  ([`e7a6ccc`](https://github.com/AnthusAI/Plexus/commit/e7a6cccdaed3ef0af30f413e409828a1a153fbb0))

### Continuous Integration

- Fixed tests after moving dashboard client code.
  ([`c44099b`](https://github.com/AnthusAI/Plexus/commit/c44099b8f33f754424b96151e003546fb24ba97a))

- Reset change log.
  ([`e5a74e6`](https://github.com/AnthusAI/Plexus/commit/e5a74e617f9787fb1e4d77cc19164158c7c78a75))

- Reset change log.
  ([`fab0c3a`](https://github.com/AnthusAI/Plexus/commit/fab0c3a8dc185e1be4163483fa5940e895e5b94c))

- Set up multi-branch releases.
  ([`c48d3b6`](https://github.com/AnthusAI/Plexus/commit/c48d3b68841e78439f57a78644b504d41f590cc1))

- **github**: Another attempt to fix Storybook CI tests.
  ([`46a7fcb`](https://github.com/AnthusAI/Plexus/commit/46a7fcb5a1f2e965e13fb3b817ca6f730ddaedfd))

- **github**: Conditional load for CI.
  ([`9b8b996`](https://github.com/AnthusAI/Plexus/commit/9b8b9964213b02a5bc8f03c711ded3cb9e4c63dd))

- **github**: Fix Storybook testing.
  ([`83f8881`](https://github.com/AnthusAI/Plexus/commit/83f888110cdf99fd707b4daed7047a1fbd59cb6d))

- **github**: Python Semantic Release.
  ([`530dba9`](https://github.com/AnthusAI/Plexus/commit/530dba9454fd39e2f55bf9dfc2b165a6e59b5c71))

- **github**: Run CI tests before releasing.
  ([`5a5b3cc`](https://github.com/AnthusAI/Plexus/commit/5a5b3cc8a0023ff7e1a4ab3d4389c822673e77e7))

- **github**: Type check instead of build in CI.
  ([`6736d0f`](https://github.com/AnthusAI/Plexus/commit/6736d0f17c58373c0893dfa3f217b523369130ac))

- **storybook**: Got Storybook interaction tests working.
  ([`caf1770`](https://github.com/AnthusAI/Plexus/commit/caf1770184008d174b7ad0eaa3a09a64385263f8))

### Features

- Add ContextExtractor node for extracting text with context
  ([`81d8ae2`](https://github.com/AnthusAI/Plexus/commit/81d8ae2e3c5e93f91cc0f10b56a0b47495345d5c))
