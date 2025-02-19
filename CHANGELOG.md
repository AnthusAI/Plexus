# CHANGELOG


## v0.6.2-alpha.1 (2025-01-23)

### Bug Fixes

- **dashboard**: Only show 100 Evaluations.
  ([`bd623c0`](https://github.com/AnthusAI/Plexus/commit/bd623c05ffdca9ca186d94d717f78fa7cd91995d))

- **dependencies**: Add missing comma in pyproject.toml dependencies list
  ([`547280d`](https://github.com/AnthusAI/Plexus/commit/547280dea49669215e9a2391777ad3a461a70592))

### Refactoring

- **tasks**: Replace 'Action' with 'Task' across components and update related logic
  ([`756dde9`](https://github.com/AnthusAI/Plexus/commit/756dde97f455df0af9a5788643999d6c3015b11e))


## v0.6.1 (2025-01-21)


## v0.6.0 (2025-01-21)


## v0.6.0-alpha.2 (2025-01-21)

### Bug Fixes

- **dashboard**: Gradient logo backgrounds on login, sidebar
  ([`d82626b`](https://github.com/AnthusAI/Plexus/commit/d82626bcd1f125f4c89a8b6e57827a1dbea1350e))


## v0.6.0-rc.1 (2025-01-21)

### Chores

- **dependencies**: Add SQLAlchemy[asyncio] version 1.4.15 to project dependencies to fix dependency
  mismatch
  ([`fe5ae21`](https://github.com/AnthusAI/Plexus/commit/fe5ae216ba805b86ba6fe4a2107ed9964ac23e7a))


## v0.6.0-alpha.1 (2025-01-21)

### Bug Fixes

- **NLTK**: Standardize tokenizer initialization across parser classes
  ([`2d48066`](https://github.com/AnthusAI/Plexus/commit/2d4806653e82d78b0e4def97e7212f94a1e90898))

- Replace direct NLTK punkt downloads with proper error handling - Add consistent
  PunktSentenceTokenizer initialization pattern - Implement private tokenizer attribute with proper
  Pydantic config - Update tokenizer usage in BeforeAfterSlicer, Extractor, and ContextExtractor -
  Fix potential race conditions in tokenizer initialization

### Chores

- **dependencies**: Update NLTK version and fix repository URL for openai-cost-calculator
  ([`6f75c59`](https://github.com/AnthusAI/Plexus/commit/6f75c59ecd1f5d02526f34e5b493ca295f2d6697))

### Features

- **dashboard**: Account settings - closes #32
  ([`d7e17d5`](https://github.com/AnthusAI/Plexus/commit/d7e17d5f33ae61b7f252a0e069522d17d72f672c))

### Refactoring

- **cloudwatch**: Enhance CloudWatchLogger with detailed AWS credentials logging and error handling.
  Added debug and warning logs for client initialization and metric logging processes to improve
  traceability and error diagnosis.
  ([`13e30fe`](https://github.com/AnthusAI/Plexus/commit/13e30feb60dfa0df4e97432f292ac0a1858dc9be))


## v0.5.0 (2025-01-19)

### Features

- **landing**: Implement responsive landing page with navigation
  ([`28e8907`](https://github.com/AnthusAI/Plexus/commit/28e89078d019623826cdd52b047c61fae4029f84))

feat(landing): implement responsive landing page with navigation


## v0.4.5 (2025-01-18)


## v0.4.4 (2025-01-17)


## v0.4.3 (2025-01-17)

### Bug Fixes

- **batching**: Find or create both BatchJob and ScoringJob.
  ([`f8ccb26`](https://github.com/AnthusAI/Plexus/commit/f8ccb26f92a6b53ec2fd32b34bad95d54a1edca3))


## v0.4.2 (2025-01-17)


## v0.4.2-alpha.3 (2025-01-18)


## v0.4.2-rc.2 (2025-01-18)

### Bug Fixes

- **logging**: Enhance AWS credentials handling in CustomLogging.py
  ([`c5eefb9`](https://github.com/AnthusAI/Plexus/commit/c5eefb904de79f413c3255c69f44e68c6af140be))

- Added a helper function `_get_aws_credentials()` to check and return AWS credentials. - Improved
  logging setup to conditionally create a CloudWatch handler based on the presence of AWS
  credentials. - Included debug prints for better visibility during AWS credentials checks and
  CloudWatch handler creation. - Updated log group and stream handling to ensure proper
  configuration before logging to CloudWatch.


## v0.4.2-alpha.2 (2025-01-17)


## v0.4.2-rc.1 (2025-01-17)

### Bug Fixes

- **logging**: Update environment variable for AWS region in CustomLogging.py
  ([`84123b2`](https://github.com/AnthusAI/Plexus/commit/84123b221a56f9429f3332cad1a84ef258fda2de))


## v0.4.2-alpha.1 (2025-01-16)

### Bug Fixes

- **packaging**: Package compatibility mode.
  ([`62f3e8a`](https://github.com/AnthusAI/Plexus/commit/62f3e8ad535461b43567c5ba245a8de26f10e16d))


## v0.4.1 (2025-01-15)


## v0.4.0 (2025-01-13)


## v0.4.0-rc.2 (2025-01-15)


## v0.4.0-alpha.3 (2025-01-14)

### Bug Fixes

- Close score result detail when selecting new evaluation
  ([`7d1a233`](https://github.com/AnthusAI/Plexus/commit/7d1a2338d69b651e9aa7dde7102e119ee85d6110))

The score result detail view now properly closes when selecting a different evaluation. This was
  achieved by: - Moving score result selection state from DetailContent to parent component - Adding
  selectedScoreResultId and onSelectScoreResult props to control visibility - Using props instead of
  internal state to determine what detail view to show


## v0.4.0-rc.1 (2025-01-13)


## v0.4.0-alpha.2 (2025-01-10)

### Bug Fixes

- **evaluations**: Handle evaluation updates correctly
  ([`f25a759`](https://github.com/AnthusAI/Plexus/commit/f25a759b75ae665405d3b67b958176ad4d491357))

- Update existing evaluations instead of skipping them - Preserve related data references during
  updates - Extract EvaluationRow component for better performance


## v0.4.0-alpha.1 (2025-01-10)

### Features

- **evaluations**: Add delete functionality and action dropdown
  ([`afff9e0`](https://github.com/AnthusAI/Plexus/commit/afff9e01fca2ea1794ca5bf465335122f6aa766c))

- Enable deleting evaluations, score results, and scoring jobs via `handleDeleteEvaluation`. - Add
  dropdown menu in each row for quick evaluation actions. - Update table layout with an "Actions"
  column for better usability. - Subscribe to delete events for automatic list updates.


## v0.3.3 (2025-01-09)


## v0.3.2 (2025-01-09)


## v0.3.2-alpha.2 (2025-01-09)

### Bug Fixes

- **dashboard**: Stay on the same page when reloading.
  ([`69874dd`](https://github.com/AnthusAI/Plexus/commit/69874dd93b3f4ffc50dd68b3ad79e67661c52b70))

- **evaluations-dashboard**: Confusion matrix filtering -- now case-insensitive.
  ([`bf68cae`](https://github.com/AnthusAI/Plexus/commit/bf68cae9d1d3f85d788fbf47c3aaa185768efd61))

### Testing

- Add CloudWatchLogger unit tests
  ([`db19395`](https://github.com/AnthusAI/Plexus/commit/db1939576b7ccb02926c63625a0b11cacd142c2b))

Tests cover AWS credential handling, metric logging, and error cases.


## v0.3.2-rc.1 (2025-01-09)

### Refactoring

- **Evaluation**: Adjust total predictions calculation based on evaluation status
  ([`f83c1c0`](https://github.com/AnthusAI/Plexus/commit/f83c1c04d3a80519f2bcb53718275637e6b72abc))

- Updated the logic to calculate total predictions based on the evaluation status. - For completed
  evaluations, the total is derived from the predicted distribution data. - For ongoing evaluations,
  the initial sample size is used instead. - Ensured that the totalItems parameter reflects the
  correct count in the update parameters.


## v0.3.2-alpha.1 (2025-01-08)

### Bug Fixes

- **evaluations-dashboard**: "unknown Score" bug.
  ([`c0c4506`](https://github.com/AnthusAI/Plexus/commit/c0c4506bd8efc7e9843a7adc155ffbc726d3f3a1))

### Refactoring

- **metrics**: Streamline final metrics logging and enhance continuous metrics computation
  ([`b74166a`](https://github.com/AnthusAI/Plexus/commit/b74166a00fb620c3b67ee5570e53b49b0115891f))

- **sync**: Update score processing to include index for order assignment
  ([`e5852bf`](https://github.com/AnthusAI/Plexus/commit/e5852bf4cf8d93ded84fb6dfdff42395200b5233))


## v0.3.1-alpha.1 (2025-01-06)


## v0.3.1 (2025-01-06)


## v0.3.1-rc.1 (2025-01-06)

### Bug Fixes

- Update environment variable for AWS region in CloudWatch logger
  ([`ac5f7ba`](https://github.com/AnthusAI/Plexus/commit/ac5f7bac82f5d8fb6d7a79ea52618b2eae2febf0))


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
