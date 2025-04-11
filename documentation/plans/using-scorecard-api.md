# Plan: Using the Scorecard API with Evaluation Commands (v2 - Dependency Aware)

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