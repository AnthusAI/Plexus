# CHANGELOG


## v0.18.0 (2025-03-20)

### Bug Fixes

- **generator**: Remove explanation from result state in Generator class
  ([`08d83b5`](https://github.com/AnthusAI/Plexus/commit/08d83b528f4965e083d9053f04b96c3cb108d1fd))

- Updated the result state creation in the `Generator` class to exclude the `explanation` field,
  ensuring only the `completion` is included in the state. This change simplifies the state
  management and aligns with the intended functionality.

### Features

- **generator**: Add Generator node for LLM completions
  ([`4a00a52`](https://github.com/AnthusAI/Plexus/commit/4a00a52d0d8ff61f73b7d3be50a8bab344ebf46c))

- Introduced a new `Generator` class in `Generator.py` that generates completions from LLM calls
  using a LangGraph subgraph. - Updated `__init__.py` to include the new `Generator` class. -
  Implemented methods for handling LLM requests, retries, and state management within the
  `Generator` class.

### Refactoring

- **documentation**: Add LogicalClassifier usage example to YAML configuration guide
  ([`64eec40`](https://github.com/AnthusAI/Plexus/commit/64eec408402d673282682db57024a3e9740de9b2))


## v0.17.0 (2025-03-19)

### Bug Fixes

- **scorecard**: Move io to top of file to solve linter error
  ([`ce41887`](https://github.com/AnthusAI/Plexus/commit/ce41887aafba48a2954b2cf20ec365a472d46275))


## v0.16.0 (2025-03-17)

### Bug Fixes

- **extractor**: Update test assertions and state handling in Extractor
  ([`d5d0cdf`](https://github.com/AnthusAI/Plexus/commit/d5d0cdf2f8d782fbb8ca04e330974445a83741b5))

- Modified test assertions to check for attributes instead of dictionary keys for better
  compatibility with object-oriented design. - Enhanced the Extractor class to include extracted
  text in the state dictionary, improving the result handling.

- **score-commands**: Update FileEditor to handle Claude's tool call parameters
  ([`b76c10f`](https://github.com/AnthusAI/Plexus/commit/b76c10f2a105d4d87079b0190537d5b7a716092b))

- Add file_text parameter to create method to match Claude's format - Allow empty strings in
  str_replace for text deletion - Improve newline handling in insert method - Update
  ScoreCommands.py to use file_text instead of content - Update tests to expect consistent newline
  behavior

This ensures compatibility with Claude's tool call format and fixes issues with empty files being
  created.

### Chores

- **dependencies**: Add langchain-anthropic to project dependencies
  ([`feb3639`](https://github.com/AnthusAI/Plexus/commit/feb36399e8c74678afa0dee91d4ff7a599f6c6b2))

- **dependencies**: Add ruamel.yaml to project dependencies for YAML handling
  ([`660cee4`](https://github.com/AnthusAI/Plexus/commit/660cee461ad47f6494e171ab3e49639d43b9c7a3))

### Features

- **chat**: `plexus score chat` - Edit Score configurations with natural language, like Cursor or
  GitHub Copilot.
  ([`d76661f`](https://github.com/AnthusAI/Plexus/commit/d76661fc1ecbcab77c44cf69646896fcaef7226c))

- **score**: Add command to list all versions for a specific score
  ([`315a808`](https://github.com/AnthusAI/Plexus/commit/315a808136e48b233b3389a69eff0530f202de0d))

- **score-commands**: Add optimize command for score prompts using AWS Bedrock
  ([`af35f45`](https://github.com/AnthusAI/Plexus/commit/af35f4555a15704a351bf230f5b7940aca005928))

- **scorecards**: Add duplicate scorecard detection and management
  ([`7b55d89`](https://github.com/AnthusAI/Plexus/commit/7b55d89a24e1a16db4b6386cbe268b7c12f21c22))

- Implement functionality to detect and clean duplicate scorecards by key - Enhance user interaction
  with prompts for deletion of duplicates - Introduce a new command to find and manage duplicate
  scorecards across the system - Improve console output for better user experience during duplicate
  checks

- **scorecards**: Enhance scorecard resolution and push functionality
  ([`068011b`](https://github.com/AnthusAI/Plexus/commit/068011b68f07158e4d3039610fb4b7b1645874d1))

- Add detailed logging and error handling to scorecard identifier resolution - Implement flexible
  scorecard lookup with multiple matching strategies - Add --create-if-missing flag to automatically
  create scorecards - Improve YAML file matching and loading for scorecard push - Enhance error
  messages and provide more informative console output

### Refactoring

- **classifier**: Enhance find_matches_in_text method to handle overlapping matches and maintain
  original index
  ([`6790a12`](https://github.com/AnthusAI/Plexus/commit/6790a12680439e183b9c2e72ea5b3eecef4a76c5))

- Updated the method to return an additional original_index in the match tuples. - Improved logic to
  prioritize longer matches when parsing from the end. - Clarified sorting strategy based on parsing
  direction to handle conflicts effectively.

- **extractor**: Enhance Extractor class: Added logging and state management for extraction results
  ([`f7c17b5`](https://github.com/AnthusAI/Plexus/commit/f7c17b5e7281da25190816eb08cddba723983313))

- **resolvers**: Add trace field to getResourceByShareToken response
  ([`72ee20a`](https://github.com/AnthusAI/Plexus/commit/72ee20af89e9b2c8222a98a0b854b74cd0b45e7e))

- **score**: Implement secondary index query for fetching all score versions
  ([`931ae55`](https://github.com/AnthusAI/Plexus/commit/931ae552bbd20fcfe1aad82406623cffd9922866))

- **score-commands**: Clean up imports and streamline dependencies in ScoreCommands.py
  ([`18498b3`](https://github.com/AnthusAI/Plexus/commit/18498b3b782ffabfba0c7b42f11e96c121983a10))

- Removed unused imports to improve code clarity and maintainability. - Organized import statements
  for better readability. - Ensured all necessary dependencies are included for functionality.

- **score-commands**: Enhance optimize function with new text editor tool and command handling
  ([`ad8ce9b`](https://github.com/AnthusAI/Plexus/commit/ad8ce9b0996dec950ac14b9cca5a305a97926adf))

- Replaced the previous tool definitions with a single official Anthropic text editor tool. -
  Updated command handling to include 'view', 'str_replace', 'create', and 'insert' commands. -
  Improved conversation tracking and error handling for tool interactions. - Added validation for
  edited YAML files and enhanced user feedback for optimization results.

- **score-commands**: Implement retry logic and enhance debug capabilities in optimize function
  ([`f0b44a3`](https://github.com/AnthusAI/Plexus/commit/f0b44a3d7ad1e41190dab30a7d92ddbd7eccb5ba))

- Added retry decorator for API calls to handle timeouts and connection errors. - Introduced a debug
  flag for more verbose output during optimization. - Improved error handling and user feedback for
  file editing processes. - Updated the initialization of the ChatAnthropic model with new
  parameters for better response control.

- **score-commands**: Update model reference and documentation in optimize function
  ([`1fb500e`](https://github.com/AnthusAI/Plexus/commit/1fb500eb1ee0de7438aa1a4ef78c5d365fc00b36))

- Changed the help text for the model option to specify it as an Anthropic model ID. - Updated the
  function docstring to clarify that optimization uses Claude AI via ChatAnthropic.

- **scorecards**: Improve YAML handling with ruamel.yaml
  ([`356c6d6`](https://github.com/AnthusAI/Plexus/commit/356c6d64f4516b64108d909e7c9a5285d6b9038c))

- Replace PyYAML with ruamel.yaml for better multi-line string preservation - Add custom YAML
  handler to maintain formatting and prevent line wrapping - Refactor YAML loading and dumping
  across pull and push methods - Enhance configuration file processing with improved YAML parsing


## v0.15.0 (2025-03-11)

### Chores

- Remove unused LangGraph ToolExecutor import
  ([`739df25`](https://github.com/AnthusAI/Plexus/commit/739df253542c246d6a672ae47c53cf41ae5184a6))

### Features

- **items**: Realtime subscription for new Items.
  ([`75d9d5f`](https://github.com/AnthusAI/Plexus/commit/75d9d5f8b31b2b13f3ff9f7e084007c4f08cb4f0))


## v0.14.0 (2025-03-10)

### Features

- **items**: Implemented items dashboard using real data.
  ([`9a29577`](https://github.com/AnthusAI/Plexus/commit/9a29577ba7703e94cadae406251e35c3ab3739e6))


## v0.13.0 (2025-03-09)

### Features

- **evaluations**: Filter evaluations by scorecard or score, using a server-side index.
  ([`03463c4`](https://github.com/AnthusAI/Plexus/commit/03463c435cda9e953a8d4aefe70b0bd126261432))


## v0.12.0 (2025-03-09)

### Bug Fixes

- **core**: Enhance dynamic class loading with plexus_extensions fallback
  ([`f93e274`](https://github.com/AnthusAI/Plexus/commit/f93e2748febe3597269be52ff841594758216af4))

- Add fallback mechanism to load classes from plexus_extensions namespace - Improve logging for
  class loading attempts - Provide more informative error messages when class resolution fails

### Features

- **langgraph**: Add node results tracking
  ([`8474e71`](https://github.com/AnthusAI/Plexus/commit/8474e71ec3dd704fa88056a3094263bff4ebf0e6))

- Introduce `node_results` field in LangGraphScore to track node execution details - Implement
  `log_state` method in BaseNode for comprehensive state logging - Update Classifier node to use new
  state logging mechanism

- **trace**: Enhance trace data handling and logging
  ([`a4ed51f`](https://github.com/AnthusAI/Plexus/commit/a4ed51f2fee06a0f38fe7101eef910c8420cf714))

- Update Evaluation.py to add trace data to score results - Modify LangGraphScore to support trace
  metadata merging - Implement comprehensive BaseNode_test.py with trace logging tests - Refactor
  BaseNode.py to improve trace metadata management


## v0.11.0 (2025-03-09)

### Features

- **CLI**: Added `plexus results list` and `info` CLI commands for examining recent score results.
  ([`1b2d786`](https://github.com/AnthusAI/Plexus/commit/1b2d7869ea44ecf21faf2b8190ea26338544797b))


## v0.10.1 (2025-03-08)

### Bug Fixes

- **share-links**: Restore evaluation share functionality
  ([`71b1189`](https://github.com/AnthusAI/Plexus/commit/71b11892d8fdb11b5bb9d8db27918c0382e6a762))

The recent URL restructuring broke the share evaluation functionality due to: 1. Authentication
  issues when fetching share links 2. Resource type case sensitivity mismatch ('Evaluation' vs
  'EVALUATION')

This fix: - Reverts to using the custom GraphQL resolver for share links with proper auth - Makes
  resource type checking case-insensitive - Adds detailed logging for better debugging

Resolves the "NoValidAuthTokens" and "Invalid resource type" errors when accessing shared
  evaluations.


## v0.10.0 (2025-03-06)

### Bug Fixes

- **evaluations**: Improve error handling for expired and revoked share links
  ([`a599dc7`](https://github.com/AnthusAI/Plexus/commit/a599dc7231995028574454c82f64b46e61c9367a))

- Add detailed error messages for expired and revoked share links - Safely handle null score results
  when standardizing evaluation data - Enhance user guidance for share link issues

- **share-links**: Remove temporary clipboard failure testing code
  ([`4cee14d`](https://github.com/AnthusAI/Plexus/commit/4cee14d39412135d6dff4a1673c1c5e46ba060fc))

- Remove hardcoded error throwing for clipboard testing - Restore standard clipboard write
  functionality

### Chores

- **backend**: Add AppSync permissions to share token resolver function
  ([`928090a`](https://github.com/AnthusAI/Plexus/commit/928090a9a3188051a53dafa0428386244c106dcc))

Configure IAM permissions for the getResourceByShareToken function to enable GraphQL access,
  supporting secure share link functionality

- **dependencies**: Update AWS SDK dependencies for request signing
  ([`eb0f6b3`](https://github.com/AnthusAI/Plexus/commit/eb0f6b36e486a81f968224e391b5ebbdcd87c536))

Synchronize package dependencies for AWS SDK libraries used in manual GraphQL request signing. This
  update: - Adds @aws-sdk/protocol-http and @aws-sdk/signature-v4 to dashboard package - Removes
  redundant package-lock and package.json from resolvers directory - Ensures consistent AWS SDK
  library versions across project

### Features

- **share-links**: Add configurable share evaluation modal
  ([`66f29dc`](https://github.com/AnthusAI/Plexus/commit/66f29dcb1f42c30af6f99b26e4e7b78d5d7ab343))

- Implement ShareEvaluationModal component for customizable evaluation sharing - Add support for
  configuring share link expiration and view options - Enhance share link creation with granular
  display and metric controls - Integrate modal into EvaluationsDashboard with improved link sharing
  workflow

### Refactoring

- **auth**: Enable unauthenticated access for share links
  ([`bcf0571`](https://github.com/AnthusAI/Plexus/commit/bcf057198b9dff628d0d11c623afff98abbb34b1))

Configure Amplify to support guest access and identity pool authentication for public evaluation
  sharing. Includes: - Updated Amplify configuration in evaluation page to allow guest access -
  Modified GraphQL query authentication mode to use identity pool

- **evaluations**: Add score results parsing for shared evaluation page
  ([`e606594`](https://github.com/AnthusAI/Plexus/commit/e606594302834c78e38647055a8d67591cfb1cc7))

- Enhance PublicEvaluation component to parse and display score results - Map score result items
  with key metadata like id, value, confidence, and itemId - Ensure backward compatibility with
  existing evaluation data structure

- **evaluations**: Enhance score result selection and logging in shared evaluation page
  ([`71847cf`](https://github.com/AnthusAI/Plexus/commit/71847cf9d101f3d306a50c35aa13371757cf9b77))

- Add state management for selected score result ID - Implement debug logging for score result
  selection - Standardize score results parsing with new utility function - Expand EvaluationTask
  component with full-width option and score result selection callback

- **evaluations**: Enhance score result selection and logging in shared evaluation page
  ([`1b9b220`](https://github.com/AnthusAI/Plexus/commit/1b9b220fcd4340c1e9d7812525520a9f93730cae))

- Add state management for selected score result ID - Implement debug logging for score result
  selection - Standardize score results parsing with new utility function - Expand EvaluationTask
  component with full-width option and score result selection callback

- **evaluations**: Remove Amplify configuration from evaluation page
  ([`52c2f0f`](https://github.com/AnthusAI/Plexus/commit/52c2f0fc7eda2222b9f7321138f6d61670e33790))

- Remove explicit Amplify configuration with guest access - Simplify imports by removing unnecessary
  Amplify setup - Maintain existing authentication and session handling

- **share-links**: Add "Never Expire" option for shared resource links
  ([`8fa7519`](https://github.com/AnthusAI/Plexus/commit/8fa751969b8b91bf6f75f8c32e2fb39602420cfb))

- Introduce "never" expiration option in share resource modal - Update state management to handle
  null expiration dates - Add conditional rendering for never-expiring link messages - Modify
  onShare callback to pass undefined for never-expiring links

- **share-links**: Add summary display mode for shared evaluations
  ([`d4edced`](https://github.com/AnthusAI/Plexus/commit/d4edced69e1e5432af2e359f8c4959c1dbc392a5))

- Implement 'summary' display mode option in getResourceByShareToken resolver - Conditionally remove
  score results when summary mode is selected - Enhance view options flexibility for shared
  evaluation resources

- **share-links**: Configure IAM authentication for share token resolver
  ([`658b8b7`](https://github.com/AnthusAI/Plexus/commit/658b8b7c265250f0bcc7472fe66e415266cd1910))

Update the share token resolver to use IAM authentication mode when generating the Amplify client,
  ensuring secure and consistent access for retrieving shared resources

- **share-links**: Enhance AppSync permissions and add request logging
  ([`9685326`](https://github.com/AnthusAI/Plexus/commit/968532624477ff4473f14fc77567092c6d3e3e54))

Expand AppSync permissions for the share token resolver function and add debug logging for GraphQL
  request details. Changes include: - Broaden IAM policy to allow all AppSync actions - Add console
  logging for request headers to aid in troubleshooting request signing

- **share-links**: Enhance share link expiration with flexible period selection
  ([`f21f07c`](https://github.com/AnthusAI/Plexus/commit/f21f07c77b5b67534332cc5f08e9f6012129bdcf))

- Add configurable expiration periods (7 days to 1 year) - Implement custom date selection for share
  link expiration - Improve UX with dropdown and calendar popover for expiration settings - Use
  date-fns for more robust date handling

- **share-links**: Generalize share modal for multiple resource types
  ([`6e96a50`](https://github.com/AnthusAI/Plexus/commit/6e96a501e9c934c883b2aa8d2cf162eccb3f6589))

- Replace ShareEvaluationModal with generic ShareResourceModal - Add support for dynamic resource
  type and name configuration - Enhance modal flexibility to handle evaluations, scorecards, and
  reports - Update EvaluationsDashboard to use new generalized sharing component

- **share-links**: Improve error handling for shared evaluation page
  ([`b53ceb6`](https://github.com/AnthusAI/Plexus/commit/b53ceb6a56378a5cc058aff57d17c6be7ee28ab4))

- Add comprehensive error handling for GraphQL and fetch errors - Enhance error display with
  context-specific messages for expired or revoked share links - Implement detailed error logging
  and user-friendly error UI - Add specific error handling for share link expiration and revocation
  scenarios

- **share-links**: Improve share link generation and clipboard handling
  ([`22b5ef3`](https://github.com/AnthusAI/Plexus/commit/22b5ef3bc60e014b138003465ed1121b71a9a00e))

- Add robust clipboard permission and error handling for share links - Introduce shareUrl state to
  manage generated share link - Update ShareResourceModal to display and copy share link - Enhance
  user feedback for share link creation and copying

- **share-links**: Improve share token resolver and evaluation fetching
  ([`baec7cf`](https://github.com/AnthusAI/Plexus/commit/baec7cfda9d4d5be8f54aeee3329131ff478178e))

Update GraphQL resolver authorization and enhance evaluation fetching logic: - Add public API key
  and authenticated access to share token resolver - Implement robust JSON parsing for share token
  evaluation data - Add comprehensive error logging and debugging for share link retrieval

- **share-links**: Migrate to manual AWS Signature v4 request signing
  ([`9ead588`](https://github.com/AnthusAI/Plexus/commit/9ead58807b62ae62e3cb17fd4e95f5591305ac2d))

Replace Amplify client with manual GraphQL request signing using AWS SDK libraries. This change: -
  Removes dependency on generateClient() - Implements direct request signing with SignatureV4 - Uses
  node-fetch for GraphQL API calls - Adds necessary AWS SDK dependencies for authentication

- **share-links**: Remove deprecated IAM client utility
  ([`c99a89a`](https://github.com/AnthusAI/Plexus/commit/c99a89a08fd368917c0cca418002b4368178e04e))

- **share-links**: Simplify evaluation fetching for shared resources
  ([`6aeb805`](https://github.com/AnthusAI/Plexus/commit/6aeb805effaefc2c8a4e0b3539737d8792cd2bc8))

Streamline the evaluation page for shared links by: - Removing redundant GraphQL query and type
  imports - Consolidating evaluation fetching logic to use share token method - Improving token
  validation and authentication mode detection - Removing unnecessary state tracking for shared
  resources

- **share-links**: Update resolver path for share token handler
  ([`d8faffd`](https://github.com/AnthusAI/Plexus/commit/d8faffdbf5a592638d75514994ece0430c6598f3))

Adjust the entry point for the share token resolver to use the correct relative path, ensuring
  proper module resolution for the share link functionality

- **ui**: Update share link icon and dropdown menu interaction
  ([`2435519`](https://github.com/AnthusAI/Plexus/commit/24355198820c7815bf4ad61acfb1159739a15e2d))

- Replace 'Eye' icon with 'Share' icon in evaluation dropdown menu - Change dropdown menu item
  cursor style from 'default' to 'pointer'

### Testing

- **evaluations**: Update PublicEvaluation component tests for share link handling
  ([`cfc0895`](https://github.com/AnthusAI/Plexus/commit/cfc0895d29ec22aaf444ef54e10274d23356fd34))

- Refactor test suite to use fetchEvaluationByShareToken method - Add comprehensive tests for share
  link error scenarios - Implement tests for expired and revoked share link handling - Remove
  redundant isShareToken test - Improve error state and loading state test coverage


## v0.9.0 (2025-02-26)

### Bug Fixes

- **evaluation**: Handle metrics array in public evaluation page
  ([`8da1176`](https://github.com/AnthusAI/Plexus/commit/8da11766e6914dd4ed60caf483c6ef1effe56624))

Modify metrics rendering to support array-based metrics structure, ensuring correct value retrieval
  for Precision, Sensitivity, and Specificity

### Documentation

- **dashboard**: Add comprehensive development guide for Plexus Dashboard
  ([`583374e`](https://github.com/AnthusAI/Plexus/commit/583374e9fe3275d3bcc23eb8b4905bb69417c51b))

Create CLAUDE.md with detailed documentation covering build commands, test commands, and code style
  guidelines for the project

### Features

- **dashboard**: Add Monaco Editor
  ([`eefbb98`](https://github.com/AnthusAI/Plexus/commit/eefbb98c13606d192e341593f18fc41f9f0b7d5a))

- **share-evaluation**: Implement public evaluation route with comprehensive testing
  ([`73e8c15`](https://github.com/AnthusAI/Plexus/commit/73e8c15bc38cde6a64f0698264a0266bd957a9eb))

- Add route files for public evaluation page and layout - Implement data fetching, transformation,
  and rendering - Create unit and end-to-end tests for route functionality - Add public link copy
  feature to evaluations dashboard - Enhance error handling and responsive design

- **share-links**: Implement share link functionality for evaluations
  ([`089b113`](https://github.com/AnthusAI/Plexus/commit/089b113d1490c2c1a576c3142d8e1397be30e74f))

Add comprehensive share link support for evaluations, including: - GraphQL custom resolver for
  fetching shared resources - Client-side share link generation and management - Enhanced public
  evaluation page to support share token access - IAM-based client for secure share link operations
  - View options and access tracking for shared evaluations

### Refactoring

- **auth**: Allow public access to single evaluation pages
  ([`69d6402`](https://github.com/AnthusAI/Plexus/commit/69d64022851a5b7974d58e0732c18a0cdbb03c9d))

Modify client-layout to permit unauthenticated access to specific evaluation routes by dynamically
  checking the pathname structure

- **evaluation**: Enhance authentication and sharing for single evaluation page
  ([`5942d14`](https://github.com/AnthusAI/Plexus/commit/5942d1404fa16bedee986b896697d74f3c5c9ffa))

- Implement dynamic authentication mode for evaluation fetching - Replace `useToast` with `sonner`
  for toast notifications - Refactor link sharing functionality with improved error handling -
  Simplify evaluation data retrieval and error management

- **evaluation**: Improve data fetching and testing for public evaluation page
  ([`074ff99`](https://github.com/AnthusAI/Plexus/commit/074ff99921f4283af13fd62941b4f955d2f9ff54))

- Introduce EvaluationService for better separation of concerns - Add comprehensive unit tests for
  PublicEvaluation component - Enhance error handling and loading state management - Implement
  dependency injection for easier testing - Optimize authentication and data fetching logic

- **share-links**: Add ShareLink model to Amplify schema
  ([`64e0dce`](https://github.com/AnthusAI/Plexus/commit/64e0dce63264cf159760e5c6ddfb271d660af40d))

Implement ShareLink model with comprehensive indexing and authorization, supporting token-based
  resource sharing functionality

### Testing

- **evaluation**: Add responsive testing utilities and unit tests for public evaluation page
  ([`ea0219f`](https://github.com/AnthusAI/Plexus/commit/ea0219f82f88b37928b405445613e14b21d4794d))

- Create test utilities for responsive design testing - Add comprehensive responsive screen size
  tests for PublicEvaluation component - Remove redundant Cypress end-to-end responsiveness test -
  Implement mockMatchMedia and resizeWindow utility functions


## v0.8.0 (2025-02-22)

### Features

- Add foreground-selected color for enhanced UI contrast
  ([`0dfa243`](https://github.com/AnthusAI/Plexus/commit/0dfa24325f94cc835245f286eec6f393924dc768))

- Introduce new `--foreground-selected` CSS variable in global styles - Update Tailwind config to
  support the new color token - Modify confusion matrix cell text color to use foreground-selected
  for high-value cells - Adjust text color threshold from 70% to 90% of max value


## v0.7.0 (2025-02-21)

### Refactoring

- **dashboard**: Consolidate task and subscription utilities
  ([`555fb48`](https://github.com/AnthusAI/Plexus/commit/555fb4813fdf9150735a94439168ecd85e696b72))

### Testing

- **extractor**: Add comprehensive test suite for Extractor node
  ([`9a1e611`](https://github.com/AnthusAI/Plexus/commit/9a1e6113ea0f6a1961cfd7b88d717e29bfc56cce))

- Implement unit tests for Extractor initialization and configuration - Cover various extraction
  scenarios including exact matching, sliding window, and model output trust - Test output parser
  with different matching strategies and confidence levels - Add end-to-end chain integration test
  with dummy model - Ensure robust testing of text extraction functionality

- **extractor**: Add pytest fixture to mock OpenAI model initialization
  ([`1c02a82`](https://github.com/AnthusAI/Plexus/commit/1c02a828b5a13c7b89efddb4750cbc4fdeae4a6e))

- Create a pytest fixture to bypass real API calls during testing - Patch Extractor's
  _initialize_model method to return a dummy output - Improve test reliability by preventing
  external API dependencies


## v0.7.0-alpha.1 (2025-02-19)

### Bug Fixes

- **evaluation**: Add random seed support for data sampling in evaluation
  ([`ed420bd`](https://github.com/AnthusAI/Plexus/commit/ed420bddc1d1ef8d528fcdd057655587825ec33b))

- Modify get_data_driven_samples() to support optional random seed for reproducible sampling -
  Update accuracy() method to pass random seed through to sampling function - Add logging for random
  seed usage and sampling details - Implement flexible sampling of dataframe with configurable
  sample size and seed

- **scorecard**: Update Scorecard to track individual score costs and tokens
  ([`e9fef87`](https://github.com/AnthusAI/Plexus/commit/e9fef87482c6691bd425e2ad1634e87de8a8af03))

### Documentation

- Add documentation pages for Items, Solutions, Task Dispatch, and update Evaluations
  ([`ce41298`](https://github.com/AnthusAI/Plexus/commit/ce41298bf75544f89b6f46fc56d38b999ba93045))

### Features

- **CLI**: Consolidated dashboard commands into one `plexus` CLI command.
  ([`30aeb1e`](https://github.com/AnthusAI/Plexus/commit/30aeb1ee5b0b2c05db1cbd80ae38d5dfe2a96f57))

- **landing**: Sexy, animated workflow pictograms.
  ([`be16f85`](https://github.com/AnthusAI/Plexus/commit/be16f85d7945a9884a8369e4f8e872dc1fb83fbe))

- **scoring**: `trust_model_output` feature for Extractor node.
  ([`97e2838`](https://github.com/AnthusAI/Plexus/commit/97e28384b6370d8c440042aa3ba784332dafef50))

- **tasks**: Lambda for triggering Celery task dispatch on creation of new Task.
  ([`6b5dd4e`](https://github.com/AnthusAI/Plexus/commit/6b5dd4e0f2d2cb2c3b57e8f21c85ff7582afdae3))

- **tasks**: Standardized task-dispatch UI components. With a re-announce feature.
  ([`daeee25`](https://github.com/AnthusAI/Plexus/commit/daeee25ee73d65caf01f8800be61f799cd6fe80b))

- **toast**: Toast notifications for task creation. More to come.
  ([`822f836`](https://github.com/AnthusAI/Plexus/commit/822f83663340e7ae8dd707af8cc0e93b8ccdf0f3))

### Refactoring

- **classifier**: Improve chat history and retry message handling
  ([`5bd8001`](https://github.com/AnthusAI/Plexus/commit/5bd80012684786ed396fce89f06b2a6e26a18d45))

- **classifier**: Simplify message handling and reset state management
  ([`dc0946a`](https://github.com/AnthusAI/Plexus/commit/dc0946ae3e857fd9cadebd3e502ec39d086de546))

- **evaluation**: Replace logger with logging module in EvaluationCommands
  ([`74974a1`](https://github.com/AnthusAI/Plexus/commit/74974a13c2d96a0070ec4bb4d20f58ec77b1adb0))

- Switch from logger to custom logging module - Import truncate_dict_strings_inner utility
  (potential future use)

- **evaluations**: Refactor evaluation listing and sorting logic to use updatedAt and limit
  evaluations to 100
  ([`2bdc07a`](https://github.com/AnthusAI/Plexus/commit/2bdc07a514effc9b86bc71f1548f891aa5d92370))

- **logging**: Standardize custom logging across dashboard CLI and evaluation modules
  ([`bd5f7b1`](https://github.com/AnthusAI/Plexus/commit/bd5f7b1abc9f5cc12c312519b9c503539147051a))

- Replace custom logger with imported logging module in dashboard CLI - Align logging approach with
  recent changes in EvaluationCommands - Remove redundant logging configuration - Ensure consistent
  logging import and usage across modules

- **scoring**: Update LangGraph workflow and account model methods
  ([`9d4aca5`](https://github.com/AnthusAI/Plexus/commit/9d4aca5fef04c405db497070ab815b6e91633c89))

- **task**: Improve task stage completion and update logic
  ([`27868c9`](https://github.com/AnthusAI/Plexus/commit/27868c9081cff2c73542a2408ad8aa3ee04803f8))

- Enhance task stage completion process with more detailed tracking - Update test to verify
  multi-step task stage and task completion - Modify stage update method to use a more robust
  datetime formatting approach

- **task**: Improve TaskProgressTracker with robust progress tracking and validation
  ([`173c71d`](https://github.com/AnthusAI/Plexus/commit/173c71de30caf7a63904c44b3f72012fadfe7556))

- Add total_items initialization support in constructor - Enhance stage initialization with
  configurable total_items - Implement stricter validation for current_items updates - Add
  pre-completion checks for unstarted stages in complete() method - Update test cases to verify
  multi-stage progress tracking

- **tests**: Refactor Scorecard and Task tests to improve mocking and test coverage
  ([`cd0d98b`](https://github.com/AnthusAI/Plexus/commit/cd0d98bb0b0449df7457d1c2640b3f236100f352))

### Testing

- **classifier**: Enhance multi-node routing and condition handling tests
  ([`5ec8bea`](https://github.com/AnthusAI/Plexus/commit/5ec8bea7d2780e2f972729a71ae93166b21b40c4))


## v0.6.2-alpha.1 (2025-01-23)

### Bug Fixes

- **scoring**: Fixed LangGraphScore bypass conditions.
  ([`9dc8c07`](https://github.com/AnthusAI/Plexus/commit/9dc8c07a906fce9c6cab2107052d7a74cd0ed1c7))

### Features

- **multi-step**: Option to visualize compiled LangGraph graph.
  ([`b57e649`](https://github.com/AnthusAI/Plexus/commit/b57e649aa81a329464dfa30db5b3ab65f907536d))


## v0.6.2 (2025-01-23)

### Bug Fixes

- **dashboard**: Only show 100 Evaluations.
  ([`bd623c0`](https://github.com/AnthusAI/Plexus/commit/bd623c05ffdca9ca186d94d717f78fa7cd91995d))


## v0.6.0-rc.1 (2025-01-21)


## v0.4.2-rc.2 (2025-01-18)


## v0.4.2-rc.1 (2025-01-17)


## v0.4.0-rc.2 (2025-01-15)


## v0.4.0-rc.1 (2025-01-13)


## v0.3.2-rc.1 (2025-01-09)

### Bug Fixes

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

### Bug Fixes

- **logging**: Enhance AWS credentials handling in CustomLogging.py
  ([`c5eefb9`](https://github.com/AnthusAI/Plexus/commit/c5eefb904de79f413c3255c69f44e68c6af140be))

- Added a helper function `_get_aws_credentials()` to check and return AWS credentials. - Improved
  logging setup to conditionally create a CloudWatch handler based on the presence of AWS
  credentials. - Included debug prints for better visibility during AWS credentials checks and
  CloudWatch handler creation. - Updated log group and stream handling to ensure proper
  configuration before logging to CloudWatch.


## v0.4.2-alpha.2 (2025-01-17)

### Bug Fixes

- **logging**: Update environment variable for AWS region in CustomLogging.py
  ([`84123b2`](https://github.com/AnthusAI/Plexus/commit/84123b221a56f9429f3332cad1a84ef258fda2de))


## v0.4.2-alpha.1 (2025-01-16)

### Bug Fixes

- **packaging**: Package compatibility mode.
  ([`62f3e8a`](https://github.com/AnthusAI/Plexus/commit/62f3e8ad535461b43567c5ba245a8de26f10e16d))


## v0.4.1 (2025-01-15)


## v0.4.0-alpha.3 (2025-01-14)

### Bug Fixes

- Close score result detail when selecting new evaluation
  ([`7d1a233`](https://github.com/AnthusAI/Plexus/commit/7d1a2338d69b651e9aa7dde7102e119ee85d6110))

The score result detail view now properly closes when selecting a different evaluation. This was
  achieved by: - Moving score result selection state from DetailContent to parent component - Adding
  selectedScoreResultId and onSelectScoreResult props to control visibility - Using props instead of
  internal state to determine what detail view to show


## v0.4.0 (2025-01-13)


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


## v0.3.1-rc.1 (2025-01-06)


## v0.3.2-alpha.2 (2025-01-09)

### Bug Fixes

- **dashboard**: Stay on the same page when reloading.
  ([`69874dd`](https://github.com/AnthusAI/Plexus/commit/69874dd93b3f4ffc50dd68b3ad79e67661c52b70))

- **evaluations-dashboard**: Confusion matrix filtering -- now case-insensitive.
  ([`bf68cae`](https://github.com/AnthusAI/Plexus/commit/bf68cae9d1d3f85d788fbf47c3aaa185768efd61))

### Refactoring

- **Evaluation**: Adjust total predictions calculation based on evaluation status
  ([`f83c1c0`](https://github.com/AnthusAI/Plexus/commit/f83c1c04d3a80519f2bcb53718275637e6b72abc))

- Updated the logic to calculate total predictions based on the evaluation status. - For completed
  evaluations, the total is derived from the predicted distribution data. - For ongoing evaluations,
  the initial sample size is used instead. - Ensured that the totalItems parameter reflects the
  correct count in the update parameters.

### Testing

- Add CloudWatchLogger unit tests
  ([`db19395`](https://github.com/AnthusAI/Plexus/commit/db1939576b7ccb02926c63625a0b11cacd142c2b))

Tests cover AWS credential handling, metric logging, and error cases.


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
