# Effort Levels for Multiagent-Loop

## Problem

The current multiagent-loop is optimized for production-quality software, which is overkill for:
- LeetCode practice problems
- Quick prototypes
- Learning exercises
- Code challenges

**Current behavior**: 2-3 hours per LeetCode problem with 40+ tests, READMEs, verification scripts, etc.
**Desired behavior**: Configurable effort level - from "quick solution" to "production ready"

## Proposed Solution: `--effort` Flag

```bash
# Quick and dirty
uv run supervisor.py --effort minimal "solve two-sum"

# Balanced (default)
uv run supervisor.py --effort moderate "solve two-sum"

# Production quality
uv run supervisor.py --effort maximum "solve two-sum"
```

## Effort Level Definitions

### 1. MINIMAL (for LeetCode, quick prototypes)

**Goal**: Working solution, fast execution (~5-15 minutes per problem)

**Pipeline**: Planner → Implementer → Tester (3 agents, no review loops)

**What changes**:
- **Planner**:
  - Brief plan (1-2 paragraphs max)
  - No self-review questions
  - Skip architectural discussions
- **Implementer**:
  - Basic solution only (no optimization variations)
  - Minimal docstring (1-2 lines + args/returns)
  - No input validation beyond what's needed
  - Type hints optional
  - Only create main solution file (no README, no verify.py)
- **Tester**:
  - 5-10 test cases (examples + edge cases)
  - No test documentation
  - Skip usage guide
  - Run tests, confirm they pass
- **Skip entirely**: Reviewer, User
- **Max iterations**: 1 (no feedback loops)

**Example output**:
```
workspace/
├── solution.py        # ~30-50 lines
└── test_solution.py   # ~50-80 lines
```

### 2. MODERATE (balanced, good for most tasks)

**Goal**: Solid solution with good practices (~30-60 minutes per problem)

**Pipeline**: Planner → Implementer → Reviewer → Tester (4 agents, 1 review loop max)

**What changes**:
- **Planner**:
  - Standard plan with key decisions
  - Brief self-review
- **Implementer**:
  - Clean solution with good docstring
  - Basic input validation
  - Type hints required
  - One solution file
- **Reviewer**:
  - Focused review (correctness + obvious bugs)
  - 1 round of fixes max
- **Tester**:
  - 10-20 test cases
  - Basic usage guide
  - Run and verify tests
- **Skip**: User agent
- **Max iterations**: 1

**Example output**:
```
workspace/
├── solution.py        # ~60-100 lines
├── test_solution.py   # ~100-150 lines
└── USAGE.md           # ~30-50 lines
```

### 3. MAXIMUM (production quality, current behavior)

**Goal**: Production-ready code with comprehensive testing (~2-3 hours)

**Pipeline**: Full 5-agent pipeline with all feedback loops

**What includes**:
- Comprehensive planning with alternatives
- Multiple implementations (basic + optimized)
- Full input validation
- Extensive docstrings
- 40+ test cases
- README, verification scripts
- Code review with multiple rounds
- Actual user testing
- Max iterations: 2-3

**Example output** (current):
```
workspace/
├── solution.py         # ~150-200 lines
├── test_solution.py    # ~250-300 lines
├── verify.py           # ~50-100 lines
├── README.md           # ~150-200 lines
└── USAGE.md            # ~100-150 lines
```

## Implementation Strategy

### 1. Add `--effort` parameter to supervisor.py

```python
parser.add_argument(
    '--effort',
    choices=['minimal', 'moderate', 'maximum'],
    default='moderate',
    help='Level of thoroughness (minimal=fast, moderate=balanced, maximum=production)'
)
```

### 2. Create effort level configurations

```python
EFFORT_CONFIGS = {
    'minimal': {
        'agents': ['planner', 'implementer', 'tester'],
        'max_iterations': 1,
        'skip_review': True,
        'skip_user': True,
        'planner_prompt_suffix': '\nIMPORTANT: Keep plan brief (2-3 paragraphs max). Focus on algorithm choice only.',
        'implementer_prompt_suffix': '\nIMPORTANT: Minimal implementation - basic solution, minimal docstring, no extra files.',
        'tester_prompt_suffix': '\nIMPORTANT: 5-10 test cases covering examples and basic edge cases. Skip usage guide.',
        'reviewer_max_rounds': 0,
    },
    'moderate': {
        'agents': ['planner', 'implementer', 'reviewer', 'tester'],
        'max_iterations': 1,
        'skip_user': True,
        'planner_prompt_suffix': '\nKeep plan focused and concise.',
        'implementer_prompt_suffix': '\nClean solution with good docstring and basic validation.',
        'tester_prompt_suffix': '\n10-20 test cases with brief usage guide.',
        'reviewer_max_rounds': 1,
    },
    'maximum': {
        'agents': ['planner', 'implementer', 'reviewer', 'tester', 'user'],
        'max_iterations': 2,
        'skip_review': False,
        'skip_user': False,
        'planner_prompt_suffix': '',
        'implementer_prompt_suffix': '',
        'tester_prompt_suffix': '',
        'reviewer_max_rounds': 3,
    }
}
```

### 3. Modify agent prompts based on effort level

```python
def get_agent_prompt(role: str, base_prompt: str, effort: str) -> str:
    """Add effort-level instructions to agent prompt."""
    config = EFFORT_CONFIGS[effort]
    suffix = config.get(f'{role}_prompt_suffix', '')
    return base_prompt + suffix
```

### 4. Conditionally skip agents

```python
def run_pipeline(task: str, effort: str):
    config = EFFORT_CONFIGS[effort]
    agents_to_run = config['agents']

    for agent in agents_to_run:
        if agent == 'reviewer' and config.get('skip_review'):
            continue
        if agent == 'user' and config.get('skip_user'):
            continue

        run_agent(agent, ...)
```

## Usage Examples

### LeetCode batch processing (minimal)
```bash
uv run supervisor.py --effort minimal --workspace fibonacci "solve fibonacci problem"
# ~5-15 minutes, basic working solution
```

### Learning project (moderate)
```bash
uv run supervisor.py --effort moderate --workspace myapp "build REST API"
# ~30-60 minutes, solid code with tests
```

### Production feature (maximum)
```bash
uv run supervisor.py --effort maximum --workspace production "add authentication"
# ~2-3 hours, production-ready with comprehensive testing
```

### Batch processing with effort level
```bash
# Modify process_leetcode_batch.sh to accept effort parameter:
./process_leetcode_batch.sh --effort minimal
# Process all 10 problems in ~1-2 hours instead of 20-25 hours
```

## Benefits

1. **Speed**: Minimal effort = 10-20x faster than current
2. **Flexibility**: Choose appropriate level for task
3. **Cost**: Less API usage for simple tasks
4. **Practicality**: Makes multiagent-loop viable for LeetCode/practice
5. **Backward compatible**: Default to 'moderate', 'maximum' preserves current behavior

## Migration Path

1. Add `--effort` parameter (default='moderate')
2. Implement EFFORT_CONFIGS
3. Modify agent prompts to include effort instructions
4. Test with a few LeetCode problems at each level
5. Update batch script to use `--effort minimal`
6. Document in README

## Expected Performance

| Effort | Time/Problem | Code Quality | Use Case |
|--------|--------------|--------------|----------|
| Minimal | 5-15 min | Working solution | LeetCode, quick prototypes |
| Moderate | 30-60 min | Good practices | Learning, side projects |
| Maximum | 2-3 hours | Production ready | Real software, critical code |

## Example: Fibonacci with Different Efforts

**Minimal** (~10 min):
- `fib.py`: 30 lines (function + minimal docstring)
- `test_fib.py`: 50 lines (5-10 tests)
- Total: ~80 lines

**Moderate** (~45 min):
- `fib.py`: 70 lines (validation + good docstring)
- `test_fib.py`: 120 lines (15 tests)
- `USAGE.md`: 30 lines
- Total: ~220 lines

**Maximum** (~2.5 hours - actual):
- `fib.py`: 70 lines
- `test_fib.py`: 124 lines (18 tests)
- `verify.py`: 67 lines
- `README.md`: 190 lines
- `USAGE.md`: lots
- Total: 400+ lines

## Implementation Priority

1. **Phase 1**: Add basic effort flag and configs (1-2 hours)
2. **Phase 2**: Implement prompt modifications (2-3 hours)
3. **Phase 3**: Test and tune each level (3-4 hours)
4. **Phase 4**: Update batch script and docs (1 hour)

**Total effort to implement**: 1 day of development

## Questions to Resolve

1. Should minimal skip type hints entirely, or require them?
2. Should minimal allow some input validation (TypeError) but skip ValueError?
3. Should we have a 4th level "ultra-minimal" with no tests at all?
4. How to handle continuous mode - should it auto-select effort based on task?
