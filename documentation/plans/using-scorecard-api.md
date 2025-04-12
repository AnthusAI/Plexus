# Plan: Using the Scorecard API with Evaluation Commands

> **Note:** All CLI commands in this plan should be run from the Call-Criteria-Python project root directory (`/Users/ryan/projects/Call-Criteria-Python`).

## Repository Structure Clarification

This project involves two separate repositories:

1. **Plexus-2 Repository** (`/Users/ryan/projects/Plexus-2`):
   - Contains the core `plexus` Python module with all the shared functionality
   - Includes the implementation of the scorecard API, evaluation framework, and CLI
   - Houses the `memoized_resolvers.py`, `EvaluationCommands.py`, and other core files
   - Development and changes to the core Plexus module happen here

2. **Call-Criteria-Python Repository** (`/Users/ryan/projects/Call-Criteria-Python`):
   - Contains client-specific code and configurations
   - Uses the Plexus module via installation or symlink
   - CLI commands are executed from this directory to use the client-specific configurations
   - The actual evaluation data and client scorecards are stored in this repository

When making changes to the core Plexus functionality (like our current task), we modify files in the Plexus-2 repository, but test the changes by running commands from the Call-Criteria-Python repository.

## 1. Overview

Currently, evaluation commands (`evaluate accuracy`, `evaluate distribution`) in the Plexus CLI primarily load scorecard configurations from local YAML files found within the `scorecards/` directory. This is done via `Scorecard.load_and_register_scorecards()`, which populates the global `scorecard_registry`. While functional, this approach requires local YAML files, doesn't fully leverage the centralized scorecard management via the API, and can be inefficient for scorecards with many scores, as it loads all of them regardless of need.

This revised plan details modifications to the evaluation commands to prioritize loading only the necessary scorecard configurations (target scores and their dependencies) directly from the API using various identifiers, while retaining the ability to load *all* configurations from local YAML files as an explicit option.

## 2. Goals

*   **API-First & Efficient Loading:** Make loading scorecards via the API the default behavior, fetching only the configurations for the specific score(s) being evaluated and their recursive dependencies.
*   **Flexible Identification:** Allow users to specify scorecards using their ID, key, name, or external ID.
*   **Backward Compatibility:** Retain the ability to load scorecards fully from local YAML files using an explicit flag.
*   **Centralized Configuration:** Evaluate scorecards based on their canonical definition stored in the dashboard (specifically, the champion versions of scores).
*   **Code Reusability:** Leverage existing identifier resolution and API client logic.
*   **Efficient Caching:** Utilize the existing caching mechanisms for scorecard/score identifiers and local file storage to minimize API calls and improve performance.

## 3. Implementation Plan

### 3.1. Command Line Interface Changes (`plexus/cli/EvaluationCommands.py`)

*   **Introduce `--yaml` flag:** Add a `--yaml` boolean flag to `evaluate accuracy` and `evaluate distribution`. Presence indicates loading the *entire* scorecard definition from a local YAML file (legacy behavior).
*   **Rename `--scorecard-name` to `--scorecard`:** Update the option name for consistency with other commands (e.g., `plexus scorecards push`, `plexus scores pull`).
*   **Update Help Text:** Modify the `--scorecard` option's help text to clarify:
    *   Without `--yaml`: Accepts scorecard ID, key, name, or external ID to load from the API.
    *   With `--yaml`: Accepts a scorecard name/key that should correspond to a definition loadable via `scorecard_registry` after scanning YAML files.

### 3.2. Existing Caching Mechanisms to Leverage

Before diving into the loading logic, it's important to understand the existing caching mechanisms that should be leveraged:

#### 3.2.1. Identifier Resolution Caching (`plexus/cli/memoized_resolvers.py`)

The codebase already implements an efficient caching system for resolving scorecard and score identifiers:

```python
# Cache for scorecard lookups
_scorecard_cache: Dict[str, str] = {}
# Cache for score lookups within scorecards
_score_cache: Dict[str, Dict[str, str]] = {}

def memoized_resolve_scorecard_identifier(client, identifier: str) -> Optional[str]:
    """Memoized version of resolve_scorecard_identifier."""
    # Check cache first
    if identifier in _scorecard_cache:
        return _scorecard_cache[identifier]
    
    # If not in cache, resolve and cache the result
    result = resolve_scorecard_identifier(client, identifier)
    if result:
        _scorecard_cache[identifier] = result
    return result

def memoized_resolve_score_identifier(client, scorecard_id: str, identifier: str) -> Optional[str]:
    """Memoized version of resolve_score_identifier."""
    # Check cache first
    if scorecard_id in _score_cache and identifier in _score_cache[scorecard_id]:
        return _score_cache[scorecard_id][identifier]
    
    # If not in cache, resolve and cache the result
    result = resolve_score_identifier(client, scorecard_id, identifier)
    if result:
        if scorecard_id not in _score_cache:
            _score_cache[scorecard_id] = {}
        _score_cache[scorecard_id][identifier] = result
    return result

def clear_resolver_caches():
    """Clear all resolver caches."""
    _scorecard_cache.clear()
    _score_cache.clear()
```

This caching system significantly reduces API calls by storing previously resolved identifiers and should be used in our implementation.

#### 3.2.2. Local Score Configuration Storage (`plexus/cli/shared.py`)

The system also has a standardized way of storing score configurations locally:

```python
def get_score_yaml_path(scorecard_name: str, score_name: str) -> Path:
    """Compute the YAML file path for a score based on scorecard and score names.
    
    This function follows the convention:
    ./scorecards/[scorecard_name]/[score_name].yaml
    """
    # Create the scorecards directory if it doesn't exist
    scorecards_dir = Path('scorecards')
    scorecards_dir.mkdir(exist_ok=True)
    
    # Create sanitized directory names
    scorecard_dir = scorecards_dir / sanitize_path_name(scorecard_name)
    scorecard_dir.mkdir(exist_ok=True)
    
    # Create the YAML file path
    return scorecard_dir / f"{sanitize_path_name(score_name)}.yaml"
```

This function is used by various commands like `score pull` and `score chat` commands to cache score configurations locally. Our implementation should leverage this existing pattern.

### 3.3. Loading Logic & Scorecard Instantiation (`plexus/cli/EvaluationCommands.py`)

This is the core change, moving away from the global registry for API loading and implementing dependency-aware loading.

*   **Explicit YAML Behavior (`--yaml` flag present):**
    *   *(No change from original behavior)*
    1.  Call `Scorecard.load_and_register_scorecards('scorecards/')` to populate the global `scorecard_registry`.
    2.  Use `scorecard_registry.get(identifier)` to retrieve the pre-registered `Scorecard` *class* based on the `--scorecard` identifier.
    3.  Instantiate the scorecard: `scorecard_instance = scorecard_class(scorecard=identifier)`.
    4.  Proceed with evaluation using `scorecard_instance`.
    5.  Handle errors (scorecard not found in registry).

*   **Default API Behavior (No `--yaml` flag):**
    1.  **Resolve Scorecard ID:**
        *   Use the provided `--scorecard` identifier.
        *   Call `memoized_resolve_scorecard_identifier(client, identifier)` to get the `scorecard_id`. Handle 'not found' errors.
    2.  **Fetch Scorecard Structure (Minimal):**
        *   Make a GraphQL API call using the resolved `scorecard_id` to fetch the basic scorecard structure.
        *   **Essential Fields:** `id`, `name`, `key`, `externalId`, and importantly, the list of all scores within its sections (`sections.items.scores.items`), including each score's `id`, `name`, `key`, `externalId`, and `championVersionId`.
        *   **Crucially, *do not* fetch `championVersion.configuration` at this stage.**
            ```graphql
            # Example Query - Fetch Structure Only
            query GetScorecardStructure($id: ID!) {
              getScorecard(id: $id) {
                id
                name
                key
                externalId
                # other scorecard fields if needed...
                sections {
                  items {
                    id
                    name
                    scores {
                      items {
                        id
                        name
                        key
                        externalId
                        championVersionId # Essential for later fetching
                        # NO configuration field here initially
                      }
                    }
                  }
                }
              }
            }
            ```
        *   Store this minimal structure data (let's call it `scorecard_structure_data`).
    3.  **Identify Required Score Names:**
        *   Determine the initial target score name(s):
            *   If the `--score-name` option is provided, use that name (or comma-separated names).
            *   If `--score-name` is *not* provided, the targets are *all* score names present in the `scorecard_structure_data`.
    4.  **Build Full Dependency List:**
        *   Temporarily parse or extract the `depends_on` information *if available* directly within the score names or structure data (if the API schema were to support it - currently unlikely, see next step).
        *   *Or, more realistically:* Acknowledge that full dependency information requires parsing configurations. This means we might need an iterative approach or accept fetching slightly more than the absolute minimum initially. **Revised approach:** Fetch configurations for the *initial target* scores first (Step 5), parse them to find direct dependencies (Step 6), then recursively fetch/parse configurations for those dependencies until the full required set is known.
    5.  **Fetch Required Configurations (Iterative/Targeted) with Local Caching:**
        *   Start with the initial target score(s).
        *   Maintain a set of `required_score_ids` and a set of `processed_score_ids`.
        *   Loop:
            *   Identify needed configurations (scores in `required_score_ids` but not `processed_score_ids`).
            *   If needed configurations exist:
                *   **Check Local Cache First:** For each score, check if its configuration already exists locally using `get_score_yaml_path(scorecard_name, score_name)` before making API calls.
                *   **If Not Cached:** Make API calls to fetch `championVersion.configuration` strings for these needed scores using their `championVersionId`s from the `scorecard_structure_data`.
                *   **Cache Retrieved Configurations:** Store the fetched configurations both in memory and on disk (following the existing pattern in `score pull` commands):
                    ```python
                    yaml_path = get_score_yaml_path(scorecard_name, score_name)
                    with open(yaml_path, 'w') as f:
                        f.write(version_data['configuration'])
                    ```
                *   Add these IDs to `processed_score_ids`.
            *   Parse the newly fetched/loaded configurations.
            *   Extract `depends_on` information from the parsed configurations.
            *   Resolve dependency names/keys to their `score_id`s using the `scorecard_structure_data`.
            *   Add any newly discovered dependency `score_id`s to the `required_score_ids` set.
            *   Repeat until no new configurations are needed.
    6.  **Parse Required Configurations:**
        *   As configurations are fetched or loaded from cache (iteratively in Step 5), parse the YAML strings (using `ruamel.yaml`) into structured score configuration dictionaries. Store these parsed configs mapped by `score_id`.
    7.  **Instantiate Scorecard Dynamically:**
        *   Create a *single* `Scorecard` *instance* directly (not a class factory).
        *   Pass the essential top-level scorecard properties (`id`, `name`, `key` etc. from `scorecard_structure_data`).
        *   Create an empty `score_registry` (a `ScoreRegistry` instance) for this scorecard instance.
        *   Iterate through the final set of `required_score_ids` and their corresponding *parsed* configuration dictionaries:
            *   For each required score, determine its Python `Score` class (from the `class` field in its parsed config).
            *   Register the score in the instance's `score_registry`: `instance.score_registry.register(cls=PythonScoreClass, properties=parsed_config_dict, name=..., key=..., id=...)`.
        *   Assign the list of parsed score configurations for *required* scores to an instance variable (e.g., `self.scores_config = required_parsed_configs`). The existing `self.scores` property might need adjustment if it expects *all* scores.
            ```python
            # Simplified conceptual instantiation
            scorecard_props = { ... extracted from scorecard_structure_data ... }
            required_configs = { score_id: parsed_config for score_id in final_required_ids }

            scorecard_instance = Scorecard(scorecard=scorecard_id) # Basic init
            scorecard_instance.properties = scorecard_props # Set properties
            scorecard_instance.scores_config = list(required_configs.values()) # Store required configs

            # Populate the instance's registry
            for score_id, config in required_configs.items():
                score_class_name = config.get('class')
                # ... (logic to import/get score_class from score_class_name) ...
                PythonScoreClass = getattr(importlib.import_module(f'plexus.scores.{score_class_name}'), score_class_name) # Example import
                scorecard_instance.score_registry.register(
                    cls=PythonScoreClass,
                    properties=config,
                    name=config.get('name'),
                    key=config.get('key'),
                    id=str(config.get('id')) # Use externalId from config as registry ID
                )
            ```
    8.  **Proceed with Evaluation:**
        *   Use the constructed `scorecard_instance` (with its `score_registry` populated only with required scores) for the evaluation. The internal dependency resolution in `score_entire_text` will use this instance-specific registry.
    9.  **Error Handling:** Implement robust error handling for API failures, missing champion versions/configurations, YAML parsing errors, and resolution failures.

### 3.4. Scorecard Class Modifications (`plexus/Scorecard.py`)

*   **`__init__` Method:** May need adjustment to correctly initialize properties (like `self.scores`, `self.properties`, `self.score_registry`) when instantiated directly with API data, rather than relying solely on class attributes set by `create_from_yaml`. It should initialize `self.score_registry = ScoreRegistry()`.
*   **`build_dependency_graph` Method:** Should ideally work with the `self.scores_config` (the list of required, parsed score dictionaries) stored on the instance. It needs access to the `name`, `id`, and `depends_on` fields within these configurations.
*   **`score_names` / `score_names_to_process`:** These methods might need to operate on `self.scores_config` instead of a class-level `cls.scores` when loaded via API.
*   **Remove `create_from_api_data`:** This class factory method is no longer needed.
*   **Remove `create_from_yaml`? (Optional):** We could potentially refactor `create_from_yaml` to use the same direct instantiation logic as the API path, just sourcing the data from the file instead of the API. This would unify the instantiation process.
*   **Ensure `get_score_result` uses `self.score_registry`:** Double-check that score lookup within the execution logic correctly uses the instance's `score_registry`.

### 3.5. Registry Usage

*   **Global `scorecard_registry`:** This registry is *not* actively used or populated when loading via the API with this revised plan. It remains populated only when the `--yaml` flag is used.
*   **Instance `score_registry`:** This registry is critical. It is populated *per Scorecard instance* during the API loading process (step 3.3.7) with *only the required scores* (target + dependencies) and their configurations/classes. This registry is used internally by the `Scorecard` instance during evaluation.

## 4. Affected Files

*   `plexus/cli/EvaluationCommands.py`: Modify `accuracy` and `distribution` commands (CLI options, loading logic).
*   `plexus/Scorecard.py`: Modify `__init__`, potentially `build_dependency_graph`, `score_names`, `score_names_to_process`. Remove `create_from_api_data`. Consider refactoring `create_from_yaml`.
*   `plexus/Registries.py`: No changes needed, but understanding the different roles is key.
*   **Leveraged Files (No Changes Needed):**
    *   `plexus/cli/memoized_resolvers.py`: Contains the caching mechanism for scorecard and score identifiers.
    *   `plexus/cli/shared.py`: Contains `get_score_yaml_path` function for local storage of score configurations.

## 5. Testing Considerations

*   Test evaluation using API identifiers (ID, key, name, external ID) for single target scores.
*   Test evaluation using API identifiers where no specific target score is given (should evaluate all scores in the scorecard, loading dependencies as needed).
*   Test evaluation using the `--yaml` flag with identifiers matching local files.
*   **Test Local Caching:** Verify that score configurations are properly cached locally and reused in subsequent calls.
*   **Test Identifier Resolution Caching:** Verify that the identifier resolution cache is working correctly by monitoring API calls.
*   Verify only necessary score configurations are fetched/parsed in the API flow (requires logging/debugging).
*   Test error handling for invalid identifiers (API and YAML modes).
*   Test error handling for API failures (structure fetch, configuration fetch).
*   Test error handling for missing champion versions or configurations for required scores.
*   Test scorecards with complex, multi-level dependencies loaded via API.
*   Verify metrics and results are consistent between API and YAML loading *if the underlying configuration is identical*.

## 6. Future Improvements

*   Optimize the fetching of required configurations (e.g., explore batched `getScoreVersion` calls if the API supports it).
*   Consider adding optional caching for *parsed* score configurations fetched via API to speed up repeated evaluations of the same scorecard version.
*   Extend this API-first, dependency-aware loading approach to other commands (`train`, `predict`, etc.).

## 7. Implementation Checklist

### Current Status Legend
- ⬜ = Not started
- 🟡 = In progress
- ✅ = Completed

### Preparation
- ✅ **Step 1: Set up testing fixtures**
  - What: Create test fixtures for scorecards with dependencies
  - Goal: Have reliable test data for implementation verification
  - Verify: Test data exists and correctly represents dependency relationships
  - Files created:
    - `plexus/tests/fixtures/scorecards/test_scorecard.yaml` - Basic scorecard with simple dependencies
    - `plexus/tests/fixtures/scorecards/test_scorecard_linear.yaml` - Linear dependency chain (A→B→C→D)
    - `plexus/tests/fixtures/scorecards/test_scorecard_complex.yaml` - Complex dependency structure with parallel branches
    - `plexus/tests/test_scorecard_dependencies.py` - Test script to validate fixtures

### CLI Options Changes
- ✅ **Step 2: Update CLI parameter names in `EvaluationCommands.py`**
  - What: Rename `--scorecard-name` to `--scorecard` in both `accuracy` and `distribution` commands
  - Goal: Align option naming with other commands
  - Verify: Run `plexus evaluate --help` from the `/Users/ryan/projects/Call-Criteria-Python` directory and confirm parameter name change

- ✅ **Step 3: Add `--yaml` flag to commands**
  - What: Add boolean `--yaml` flag to both `accuracy` and `distribution` commands
  - Goal: Allow explicit request for loading from local YAML files
  - Verify: Run `plexus evaluate --help` from the `/Users/ryan/projects/Call-Criteria-Python` directory and confirm flag is present with correct help text

### Identifier Resolution & Local Caching
- ✅ **Step 4: Verify existing identifier caching**
  - What: Add logging to track cache hits/misses in `memoized_resolvers.py` in the Plexus-2 repository
  - Goal: Confirm identifier resolution caching is working correctly
  - Implementation:
    1. Modified `/Users/ryan/projects/Plexus-2/plexus/cli/memoized_resolvers.py` to add debug logging
    2. Added log messages for cache hits: `logging.debug(f"Cache HIT for scorecard identifier: {identifier}")`
    3. Added log messages for cache misses: `logging.debug(f"Cache MISS for scorecard identifier: {identifier}")`
    4. Added similar logging for score identifier resolution
    5. Added logging for cache clearing operations
  - Verify: Run commands with same identifier multiple times from the `/Users/ryan/projects/Call-Criteria-Python` directory and see cache hits in logs

- ✅ **Step 5: Verify existing local file storage**
  - What: Test score configuration saving/loading using `get_score_yaml_path`
  - Goal: Confirm local file storage pattern works as expected
  - Implementation:
    1. Created a verification script `verify_id_resolution_and_cache.py` to test both identifier resolution caching and local file storage
    2. Script tests scorecard ID resolution, score ID resolution, and verifies that caching improves performance
    3. Script retrieves score configurations from API and saves them locally using `get_score_yaml_path`
    4. Fixed GraphQL client issue: updated script to use context manager pattern for GraphQL execution:
       ```python
       # Changed from:
       result = client.execute(query)
       
       # To:
       with client as session:
           result = session.execute(gql(query))
       ```
    5. Updated `identifier_resolution.py` to use the same context manager pattern for consistent GraphQL execution
    6. Added proper exception handling for TransportQueryError
  - Verify: Successfully ran verification script from `/Users/ryan/projects/Call-Criteria-Python`, confirming:
    - Identifier resolution caching works (2nd lookups are faster)
    - Score configurations are correctly saved to local YAML files
    - Configurations are saved in expected directory structure: `scorecards/<scorecard_name>/<score_name>.yaml`
  - Notes for future implementation: 
    - Always use the context manager pattern for GraphQL client execution to avoid "Must provide document" errors
    - Be aware of the directory structure created by `get_score_yaml_path`: it organizes files by scorecard name first

### Core Loading Logic
- ✅ **Step 6: Implement scorecard structure fetching**
  - What: Add code to fetch scorecard structure without full configurations
  - Goal: Retrieve minimal data needed to identify scores and relationships
  - Implementation:
    1. Created direct memoized resolver functions that don't rely on context managers
    2. Implemented `fetch_scorecard_structure` function to retrieve scorecard data
    3. Included all essential fields (ID, name, key, sections, scores) but omitted configurations
    4. Added proper error handling and logging
    5. Created verification script to test with different identifier types
  - Verify: Structure data contains required fields (ids, names, champion version ids) when tested from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ✅ **Step 7: Implement target score identification**
  - What: Add logic to identify target scores from command options or all scores
  - Goal: Determine which scores need to be evaluated
  - Implementation:
    1. Created `identify_target_scores` function to process requested score names
    2. Added support for finding scores by name, key, ID or external ID
    3. Implemented fallback to all scores when no specific scores found
    4. Added proper logging and error handling
    5. Created verification script to test different score name scenarios
  - Verify: Correct scores are identified based on command options when run from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ✅ **Step 8: Implement local cache checking**
  - What: Add code to check if score configurations exist locally before API calls
  - Goal: Avoid unnecessary API calls for cached configurations
  - Implementation:
    1. Created `check_local_score_cache` function to check for local YAML files
    2. Used `get_score_yaml_path` to determine expected file locations
    3. Added proper logging with different levels for cached/non-cached items
    4. Added summary statistics for caching percentage
    5. Created verification script to test with different caching scenarios
  - Verify: API calls are skipped when configurations exist locally by running tests from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ✅ **Step 9: Implement configuration retrieval with caching**
  - What: Add code to fetch and cache missing configurations
  - Goal: Retrieve and store score configurations efficiently
  - Implementation:
    1. Created `fetch_score_configurations` function to fetch and cache missing configurations
    2. Used results from `check_local_score_cache` to determine what needs fetching
    3. Made API calls only for uncached configurations
    4. Added YAML validation and proper formatting when storing on disk
    5. Implemented `load_cached_configurations` to load all configurations after fetching
    6. Created verification script with mock API client to test the functionality
  - Verify: Configurations are fetched when needed and stored locally when commands are run from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ✅ **Step 10: Implement dependency discovery**
  - What: Add code to parse configurations and extract dependencies
  - Goal: Build complete dependency graph for required scores
  - Implementation:
    1. Created `dependency_discovery.py` with three main functions:
       - `extract_dependencies_from_config`: Parses YAML to find dependencies
       - `discover_dependencies`: Recursively builds complete dependency graph
       - `build_name_id_mappings`: Creates mappings between score names and IDs
    2. Handled both list-style and dictionary-style dependencies
    3. Created verification script with test cases for different fixture types
    4. Added proper logging for dependency discovery process
    5. Successfully tested with complex nested dependency structures
  - Verification: All dependencies are correctly identified and resolved when testing from the `/Users/ryan/projects/Call-Criteria-Python` directory
  - Files created:
    - `plexus/cli/dependency_discovery.py` - Core implementation
    - `verify_dependency_discovery.py` - Test script

- ✅ **Step 11: Implement iterative configuration fetching**
  - What: Add logic to iteratively fetch dependencies until all are resolved
  - Goal: Ensure all required configurations are available
  - Implementation:
    1. Created `iterative_config_fetching.py` with the main function `iteratively_fetch_configurations`
    2. Implemented multi-iteration process for dependency discovery and fetching
    3. Added logic to detect new dependencies and fetch their configurations
    4. Integrated with the existing caching mechanisms
    5. Created verification script to test the end-to-end process
    6. Fixed GraphQL client issues related to query execution
  - Verification: Complete dependency chain is fetched and cached when running from the `/Users/ryan/projects/Call-Criteria-Python` directory
  - Files created:
    - `plexus/cli/iterative_config_fetching.py` - Core implementation
    - `verify_iterative_fetching.py` - Test script

### Scorecard Instantiation
- ✅ **Step 12: Modify Scorecard instantiation for API data**
  - What: Update `Scorecard` class to work with directly instantiated API data
  - Goal: Create scorecard instances from API data without class factory
  - Implementation:
    1. Created an alternative initialization path in `__init__` that accepts `api_data` and `scores_config` parameters
    2. Implemented `initialize_from_api_data()` method to process score configurations and register them in the instance's registry
    3. Added instance-level versions of `score_names()` and `score_names_to_process()` methods to support both class and instance configurations
    4. Modified `build_dependency_graph()` to use instance-level scores when available
    5. Added defensive coding with `.get()` for properties access to handle varying data structures
    6. Created `create_instance_from_api_data()` static method for convenient instantiation from API data
  - Verify: Scorecard instances can now be created directly from API data in tests run from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ✅ **Step 13: Implement score registry population**
  - What: Add code to populate instance-specific score registry
  - Goal: Register only required scores in the instance registry
  - Implementation:
    1. This functionality was implemented as part of Step 12 in the `initialize_from_api_data()` method
    2. The method iterates through provided score configurations and registers each score in the instance's registry
    3. Each score is registered with its properties, name, key, and ID
    4. The registry is properly initialized as a fresh `ScoreRegistry` instance for each scorecard instance
    5. Added a fallback for missing scores or import errors to ensure resilience
  - Verify: Instance registry contains only needed scores with correct configurations when tested from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ✅ **Step 14: Ensure compatibility with dependency resolution**
  - What: Test/fix dependency resolution with instance registry
  - Goal: Ensure existing dependency resolution works with new approach
  - Implementation:
    1. Created a verification script `verify_instance_dependencies.py` to test dependency resolution
    2. Tested dependency graph building with simple and linear dependency structures
    3. Verified that complex dependencies with multiple levels are correctly resolved
    4. Tested conditional dependencies with different operators (==, in) and values
    5. Confirmed that `check_dependency_conditions` method works with instance-based scorecards
    6. Added defensive handling in the `build_dependency_graph` method to handle both class and instance scores
  - Verify: Dependencies resolve correctly during evaluation when running from the `/Users/ryan/projects/Call-Criteria-Python` directory

### Integration & Testing
- ✅ **Step 15: Integrate API path into command handler**
  - What: Connect new loading logic to command handler with flag check
  - Goal: Switch between API and YAML loading based on flags
  - Implementation:
    1. Created a unified loading approach in both `accuracy` and `distribution` commands
    2. Added conditional logic to check the `--yaml` flag
    3. When `--yaml` is true: use legacy approach with `load_and_register_scorecards` and `scorecard_registry`
    4. When `--yaml` is false: use new approach with `load_scorecard_from_api` function
    5. Ensured both paths create compatible scorecard instances
    6. Added detailed error messages and handling for API errors
    7. Updated the `distribution` command to use instance-based scorecard instead of class
  - Verify: Commands work with both loading approaches when run from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ✅ **Step 16: Implement error handling**
  - What: Add robust error handling for API failures, missing data, etc.
  - Goal: Ensure graceful failure and helpful error messages
  - Implementation:
    1. Added detailed error handling with specific messages for each failure mode:
       - Scorecard identifier resolution failures
       - API connectivity issues
       - Missing score configurations
       - Invalid or missing champion versions
       - Scorecard instantiation errors
    2. Used try/except blocks around each major operation in the loading process
    3. Added helpful user messages that suggest possible solutions
    4. Maintained proper error propagation with `raise ... from e` pattern
    5. Used both logging (for detailed debugging) and click.echo (for user messages)
    6. Added special handling for different error types to avoid duplicate messages
  - Verify: Commands fail gracefully with clear error messages when tested from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ✅ **Step 17: End-to-end testing with single scores**
  - What: Test evaluation with single target scores via API
  - Goal: Confirm basic functionality works
  - Implementation:
    1. Created verification script `verify_evaluation_api_loading.py` to test API-based scorecard loading
    2. Tested with different identifier types (name, key) for scorecard identification
    3. Tested explicit score selection with `--score-name` parameter
    4. Tested caching performance improvements on subsequent runs
    5. Tested error handling with invalid scorecard identifiers
    6. Fixed issues with client initialization and error handling
  - Verification: 
    - Distribution command passes testing with API-based scorecard loading
    - Scorecard loading via API is now functional with proper identifier resolution
    - Local caching of configurations works properly
    - Error handling provides appropriate messages for identification failures
  - Progress: 4 out of 7 tests are now passing. The following issues need to be addressed in subsequent steps:
    - YAML flag loading is not working correctly
    - Caching is not showing performance improvements
    - Error messages for invalid scorecards need improvement

- 🟡 **Step 17A: Fix YAML flag loading**
  - What: Fix issues with loading scorecards via the YAML flag
  - Goal: Ensure backward compatibility with local YAML files
  - Implementation Tasks:
    1. Debug why the `--yaml` flag test is failing in the verification script
    2. Fix how scorecards are registered and instantiated when using the `--yaml` flag
    3. Ensure proper error handling when local YAML files are missing or invalid
    4. Add proper logging for the YAML loading path
  - Verification: The test for accuracy command with `--yaml` flag should pass

- ⬜ **Step 17B: Improve caching performance**
  - What: Enhance caching mechanism to improve performance on subsequent runs
  - Goal: Demonstrate measurable performance improvements from caching
  - Implementation Tasks:
    1. Add detailed logging to track which parts of the process are using cached data
    2. Ensure configurations are correctly cached locally
    3. Optimize the cached data loading process
    4. Measure and document performance differences between initial and subsequent runs
  - Verification: The caching performance test should show faster execution on the second run

- ⬜ **Step 17C: Enhance error handling for invalid identifiers**
  - What: Improve error messages for invalid scorecard identifiers
  - Goal: Provide clear and helpful error messages to users
  - Implementation Tasks:
    1. Update error handling in scorecard identifier resolution
    2. Ensure consistent error message patterns across all commands
    3. Add specific suggestions for fixing common issues
    4. Add more context to error messages (e.g., what was being attempted)
  - Verification: The invalid scorecard handling test should pass with expected error message content

- ⬜ **Step 18: End-to-end testing with dependencies**
  - What: Test evaluation with scores that have dependencies
  - Goal: Confirm dependency resolution works correctly
  - Verify: All dependencies are loaded and evaluation results are correct when tested from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ⬜ **Step 19: Performance testing**
  - What: Test performance with and without caching
  - Goal: Confirm caching improves performance
  - Verify: Second runs are faster due to cache hits when running from the `/Users/ryan/projects/Call-Criteria-Python` directory

- ⬜ **Step 20: Documentation update**
  - What: Update command documentation with new options
  - Goal: Ensure users understand the new capabilities
  - Verify: Help text is clear and comprehensive when running commands from the `/Users/ryan/projects/Call-Criteria-Python` directory

## Current Status Update

Based on the verification script results from Step 17, we've made significant progress with the API-based scorecard loading functionality. 4 out of 7 tests are now passing, specifically:

1. ✅ Accuracy command with scorecard name
2. ✅ Accuracy command with scorecard key 
3. ✅ Accuracy command with specific score
4. ✅ Distribution command

The following tests are still failing:
1. ❌ Accuracy command with YAML flag
2. ❌ Caching performance improvement
3. ❌ Invalid scorecard error handling

We're now breaking these issues into separate steps (17A, 17B, 17C) to address them individually before moving on to more complex testing with dependencies in Step 18.