# Plexus Score Chat Command Plan

## Overview
The `plexus score chat` command implements an interactive REPL using Rich that creates a ReAct agent loop for working with Plexus scores. This command builds on existing functionality from `score optimize` and `scorecard pull/push` commands, with a focus on individual score version management. The system now supports both CLI REPL and Celery-based API interfaces.

## Core Requirements

### 1. Individual Score Version Management ✅
- ✅ Implement `plexus score pull` command to fetch individual score versions as YAML files
- ✅ Implement `plexus score push` command to update individual score versions from YAML files
- ✅ Store score versions in a structured directory format (e.g., `scorecards/<scorecard_name>/<score_name>.yaml`)

### 2. Plexus Tool Implementation ✅
- ✅ Create a Plexus tool class that provides methods for:
  - ✅ `list_scorecards()`: List available scorecards
  - ✅ `pull_score()`: Pull a specific score version
  - ✅ `push_score()`: Push a score version update
- ✅ Implement proper error handling and validation
- ✅ Support authentication and API client management

### 3. Rich REPL Implementation ✅
- ✅ Create a Rich-based REPL interface
- ✅ Implement command history and navigation
- ✅ Support syntax highlighting for YAML content
- ✅ Provide clear visual feedback for actions and errors

### 4. ReAct Agent Loop ✅
- ✅ Create a ReAct agent that can:
  - ✅ Use the Plexus tool for score operations
  - ✅ Use the file editor tool for YAML modifications
  - ✅ Maintain conversation context
  - ✅ Follow the ReAct pattern (Thought, Action, Observation)
- ✅ Implement proper tool result handling and error recovery

### 5. Initial Interaction Flow ✅
- ✅ Start with a canned request to Claude asking it to:
  - ✅ Describe the current score configuration
  - ✅ Ask the user what changes they'd like to make
- ✅ Hide the initial request from the user
- ✅ Present Claude's response in a clear, formatted way

### 6. Celery Integration ✅
- ✅ Implement Celery task-based interface
- ✅ Support session management and persistence
- ✅ Add task status tracking and progress updates
- ✅ Integrate with Dashboard task system

## Implementation Status

### Completed Features ✅
1. Core chat functionality with Claude AI
2. File editing and YAML manipulation
3. Session management and persistence
4. Both CLI REPL and Celery API interfaces
5. Dashboard task integration
6. Error handling and recovery
7. Testing infrastructure

### In Progress 🚧
1. Enhanced version management UI
2. Collaborative editing features
3. Template management system

### Planned Features 📋
1. Batch operations support
2. Version comparison tools
3. Advanced conflict resolution

## Implementation Milestones

### Milestone 1: Score Version Management ✅
1. ✅ Create `score pull` command
   - ✅ Implement YAML file generation
   - ✅ Add proper error handling
2. ✅ Create `score push` command
   - ✅ Implement YAML file reading
   - ✅ Handle version updates
   - ✅ Add validation

### Milestone 2: Plexus Tool
1. Create Plexus tool class
   - Implement core methods
   - Add error handling
   - Add authentication support
2. Add tool documentation
3. Add tests

### Milestone 3: Rich REPL
1. Create basic REPL structure
2. Implement command history
3. Add syntax highlighting
4. Add visual feedback

### Milestone 4: ReAct Agent
1. Create agent loop structure
2. Implement tool integration
3. Add conversation management
4. Add error recovery

### Milestone 5: Integration
1. Connect all components
2. Add comprehensive error handling
3. Add user documentation
4. Add tests

## Technical Details

### Directory Structure
```
scorecards/
  <scorecard_name>/
    <score_name>.yaml
```

### Tool Interface
```python
class PlexusTool:
    def list_scorecards(self) -> List[Dict]:
        """List available scorecards."""
        pass

    def pull_score(self, scorecard: str, score: str, version: Optional[str] = None) -> str:
        """Pull a score version as YAML."""
        pass

    def push_score(self, scorecard: str, score: str, yaml_path: str) -> str:
        """Push a score version from YAML."""
        pass
```

### ReAct Loop Structure
```python
def react_loop():
    while True:
        # Get Claude's thought
        thought = get_claude_thought()
        
        # Get Claude's action
        action = get_claude_action()
        
        # Execute action
        result = execute_action(action)
        
        # Get Claude's observation
        observation = get_claude_observation(result)
        
        # Update conversation context
        update_context(thought, action, observation)
```

## Testing Strategy
1. ✅ Unit tests for each component
2. ✅ Integration tests for the full workflow
3. ✅ Mock tests for API interactions
4. ✅ End-to-end tests for the REPL
5. ✅ Celery task testing utilities

## Documentation
1. ✅ Command usage documentation (`score-chat-celery.md`)
2. ✅ YAML format documentation
3. ✅ Tool API documentation
4. ✅ Example workflows
5. ✅ Celery integration guide

## Future Enhancements
1. Support for batch operations
2. Version comparison tools
3. Score template management
4. Collaborative editing support

## Next Steps (Deferred Items)
1. Version History Management
   - Implement version history tracking
   - Add support for viewing version history
   - Add ability to switch between versions
   - Add version comparison functionality
2. Parent-Child Relationships
   - Implement proper version lineage tracking
   - Add support for branching and merging versions
   - Add visualization of version relationships
3. Version Management UI
   - Add interactive version selection
   - Add version diff viewer
   - Add version merge conflict resolution