# Plexus Procedure Examples

This directory contains working examples of Plexus procedures using the Lua DSL v4.

## Working Examples

### 1. limerick_writer.yaml - Basic Agent Loop

**Purpose**: Demonstrates a basic AI agent loop with Human-in-the-Loop (HITL) messaging integration.

**What it demonstrates**:
- Single agent with tool calling
- Basic agent loop: `repeat Agent.turn() until Tool.called("done")`
- Rich HITL notifications with collapsible sections
- Graph node creation for storing outputs
- Output validation with structured schema
- Error handling and status reporting

**Key features**:
- **Start notification**: Informs user when workflow begins
- **Completion notification**: Shows the generated limerick with metadata in collapsible sections
- **Error notification**: Reports failures with iteration count

**How to run**:
```bash
plexus procedure run <procedure-id>
```

Or from YAML file:
```bash
python -c "from plexus.cli.procedure.service import create_procedure_from_yaml; create_procedure_from_yaml('plexus/procedures/limerick_writer.yaml')"
```

**Expected behavior**:
1. User sees start notification
2. Agent loop runs (typically 1 iteration)
3. User sees completion notification with the generated limerick

### 2. creative_writer.yaml - Multi-Agent Collaboration

**Purpose**: Demonstrates sequential multi-agent collaboration with state passing.

**What it demonstrates**:
- **Three specialized agents**: Brainstormer, Critic, Writer
- **Sequential pipeline**: Each agent builds on previous work
- **State passing between agents**: Results flow through the workflow
- **Message injection**: Using `Agent.turn({inject = "message"})` to pass context
- **Isolated conversation histories**: Each agent maintains its own conversation
- **Multi-phase HITL notifications**: User sees progress at each stage

**Key features**:
- **Brainstormer**: Generates 3-5 creative ideas about a topic
- **Critic**: Evaluates ideas and selects the strongest 1-2
- **Writer**: Creates a final piece based on selected ideas

**How to run**:
```bash
plexus procedure run --yaml plexus/procedures/creative_writer.yaml
```

**Expected behavior**:
1. User sees "Starting creative writing process" with topic
2. User sees "Evaluating ideas" progress
3. User sees "Writing final piece" progress
4. User sees "Creative writing complete!" with the final 2-3 paragraph piece

**Key pattern demonstrated**:
```lua
-- Phase 1: First agent
repeat
    Brainstormer.turn()
until Tool.called("done")
local ideas = Tool.last_call("done").args.reason

-- Phase 2: Second agent receives first agent's output
Critic.turn({inject = "Ideas to evaluate:\n\n" .. ideas})
repeat
    Critic.turn()
until Tool.called("done")
local critique = Tool.last_call("done").args.reason

-- Phase 3: Third agent receives second agent's output
Writer.turn({inject = "Selected ideas:\n\n" .. critique})
repeat
    Writer.turn()
until Tool.called("done")
```

## Directory Structure

```
plexus/procedures/
├── README.md                    # This file
├── limerick_writer.yaml         # Basic agent loop example
├── docs/                        # Generated documentation
│   ├── index.html
│   ├── getting-started.html
│   ├── api-reference.html
│   ├── examples.html
│   ├── hitl-guide.html
│   └── message-classification.html
└── AGENTS.md                    # Agent system documentation
```

## Adding New Examples

When adding new working examples:

1. Save the `.yaml` file in this directory
2. Add a section to this README describing:
   - Purpose
   - What it demonstrates
   - How to run it
   - Expected behavior
3. Ensure the example includes appropriate HITL messaging
4. Test that it runs successfully before committing

## Documentation

See `docs/` directory for comprehensive HTML documentation on:
- Getting started with procedures
- API reference
- HITL guide
- Message classification system
