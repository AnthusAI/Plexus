# CLI and MCP Standardization Plan

## Overview

This plan addresses inconsistencies between the Plexus CLI commands and MCP tool names, ensuring both interfaces follow the same naming conventions and provide equivalent functionality.

## Current State Analysis

### CLI Command Pattern
The CLI follows: `plexus <noun> <action>` where:
- **Nouns**: score/scores, scorecard/scorecards, item/items, task/tasks, report, feedback
- **Actions**: info, list, last, delete, pull, push, versions, etc.

### MCP Tool Pattern Issues
Current MCP tools use inconsistent naming:
- `find_plexus_score` (should be `plexus_score_info`)
- `get_plexus_*` prefix pattern (should use CLI action names)
- `list_plexus_*` prefix pattern (should be `plexus_*_list`)
- `get_latest_*` pattern (should be `plexus_*_last`)

## Phase 1: MCP Tool Renaming (Priority 1)

### Score Tools
```bash
# Current → Target
find_plexus_score                     → plexus_score_info
get_plexus_score_details              → plexus_score_info (merge with above)
get_plexus_score_configuration        → plexus_score_configuration
pull_plexus_score_configuration       → plexus_score_pull
push_plexus_score_configuration       → plexus_score_push
update_plexus_score_configuration     → plexus_score_update
delete_plexus_score                   → plexus_score_delete
```

### Scorecard Tools
```bash
# Current → Target
list_plexus_scorecards               → plexus_scorecards_list
get_plexus_scorecard_info            → plexus_scorecard_info
```

### Item Tools
```bash
# Current → Target
get_latest_plexus_item               → plexus_item_last
get_plexus_item_details              → plexus_item_info
```

### Task Tools
```bash
# Current → Target
get_latest_plexus_task               → plexus_task_last
get_plexus_task_details              → plexus_task_info
```

### Report Tools
```bash
# Current → Target
get_latest_plexus_report             → plexus_report_last
get_plexus_report_details            → plexus_report_info
list_plexus_reports                  → plexus_reports_list
list_plexus_report_configurations    → plexus_report_configurations_list
```

### Feedback Tools (Already Correct)
These follow the correct pattern:
- `plexus_feedback_analysis` ✓
- `plexus_feedback_find` ✓
- `plexus_predict` ✓

## Phase 2: CLI Standardization (Priority 2)

### Group Name Consistency
**Current Issue**: Both singular and plural forms exist
- `score` + `scores`
- `item` + `items` 
- `task` + `tasks`
- `scorecard` + `scorecards`

**Solution**: Standardize on plural as primary, singular as alias
```python
# In CommandLineInterface.py
cli.add_command(scorecards)  # Primary
cli.add_command(scorecard)   # Alias (points to scorecards)

cli.add_command(scores)      # Primary  
cli.add_command(score)       # Alias (points to scores)

cli.add_command(items)       # Primary
cli.add_command(item)        # Alias (points to items)

cli.add_command(tasks)       # Primary
cli.add_command(task)        # Alias (points to tasks)
```

### Action Standardization
Ensure all command groups have consistent actions:

**Standard Actions:**
- `info` - detailed information about one item
- `list` - list multiple items with filtering  
- `last` - get most recent item
- `delete` - remove items
- `pull`/`push` - for configurations
- `versions` - for versioned items

**Missing Actions to Add:**
- `plexus items last` (exists)
- `plexus tasks last` (exists)
- `plexus reports last` (exists)
- `plexus scores versions` (exists for individual scores)

### Option Name Consistency
Standardize common options across all commands:

**Account Options:**
- Use `--account` consistently (not `--account-id`, `--account-key`)
- Accept ID, name, or key formats

**List Options:**
- `--limit` for maximum results
- `--all` flag for showing all records (bypass limit)

**Info Options:**
- `--id` for specific item lookups
- `--show-*` flags for additional data (e.g., `--show-score-results`)

## Implementation Tasks

### Task 1: MCP Tool Renaming
**Files to modify:**
- `MCP/plexus_fastmcp_server.py` - Update all function names and decorators
- Test all renamed tools work correctly
- Update any internal references

**Validation:**
- All existing MCP tool calls should work with new names
- No functionality should be lost in renaming
- Parameter handling should remain identical

### Task 2: CLI Group Restructuring  
**Files to modify:**
- `plexus/cli/CommandLineInterface.py` - Update command registration
- Individual command files - Ensure consistent action names
- Update help text and documentation

**Validation:**
- All existing CLI commands continue to work
- New standardized commands work correctly
- Backward compatibility maintained through aliases

### Task 3: Option Standardization
**Files to modify:**
- All `*Commands.py` files in `plexus/cli/`
- Standardize option names and help text
- Ensure consistent parameter handling

**Validation:**
- All commands accept standardized options
- Help text is consistent across commands
- Error messages use consistent language

## Testing Requirements

### MCP Testing
```bash
# Test each renamed tool category
plexus_score_info --help
plexus_scorecards_list --help  
plexus_item_last --help
plexus_task_info --help
plexus_report_last --help

# Test actual functionality
plexus_score_info scorecard="Test" score="TestScore"
plexus_scorecards_list identifier="Test"
```

### CLI Testing  
```bash
# Test plural forms (primary)
plexus scorecards list
plexus scores info
plexus items last
plexus tasks info

# Test singular forms (aliases)
plexus scorecard list  
plexus score info
plexus item last
plexus task info

# Test option consistency
plexus scorecards list --account test --limit 5
plexus items info --id test-id --show-score-results
```

## Documentation Updates

### MCP Documentation
- Update MCP server README with new tool names
- Update any example usage in documentation
- Create migration guide for existing MCP clients

### CLI Documentation  
- Update CLI help text and examples
- Ensure command reference documentation is current
- Add examples showing both plural and singular usage

## Migration Considerations

### Backward Compatibility
- Keep old MCP tool names as deprecated aliases initially
- Provide clear migration path in documentation
- Consider deprecation timeline (e.g., 3 months notice)

### User Communication
- Announce changes in changelog
- Provide clear before/after examples
- Document benefits of standardization

## Success Criteria

### Phase 1 (MCP Alignment)
- [ ] All MCP tools follow `plexus_<noun>_<action>` pattern
- [ ] No functionality lost in renaming
- [ ] All tools tested and working
- [ ] Documentation updated

### Phase 2 (CLI Standardization)  
- [ ] Plural forms are primary command groups
- [ ] Consistent actions across all groups
- [ ] Standardized option names
- [ ] Backward compatibility maintained
- [ ] Help text is consistent

### Overall Success
- [ ] CLI and MCP interfaces use identical naming conventions
- [ ] Users can easily predict tool/command names
- [ ] Documentation is clear and consistent
- [ ] No breaking changes for existing users

## Timeline Estimate

**Phase 1 (MCP Renaming)**: 1-2 development sessions
- Rename functions in MCP server
- Test functionality
- Update documentation

**Phase 2 (CLI Standardization)**: 2-3 development sessions  
- Restructure command groups
- Standardize options
- Comprehensive testing
- Documentation updates

**Total**: 3-5 development sessions for complete standardization

## Notes

- This plan prioritizes consistency and user experience
- Changes should be backward compatible where possible
- Focus on making the interface predictable and logical
- Consider this an investment in long-term maintainability 