# LeetCode Processing: Old Experiment vs. Multiagent-Loop

## Comparison Summary

| Aspect | Old Experiment (~/data/leetcode) | New Multiagent-Loop |
|--------|----------------------------------|---------------------|
| **Architecture** | Script-based pipeline with `ftl-*-agent` tools | Multi-agent system with Claude CLI instances |
| **Agents** | 3 specialized tools (doc-agent, pytest-agent) | 5 autonomous agents (Planner, Implementer, Reviewer, Tester, User) |
| **Coordination** | Bash script orchestration | Git-based coordination with commits per stage |
| **Feedback Loops** | None - linear pipeline | 3 feedback loops (Reviewer→Implementer, Tester→Implementer, User→Planner) |
| **Documentation** | Docstring generation only | Full planning, implementation notes, reviews, usage guides |
| **Testing** | Auto-generated pytest tests | Comprehensive tests + manual verification + actual usage |
| **Code Quality** | Type hints + docstrings | Type hints + docstrings + error handling + input validation |
| **Iteration** | Single pass | Multiple iterations until user satisfied |
| **Audit Trail** | Processing logs in .txt files | Git commits + structured markdown artifacts |
| **Self-Review** | None | Every agent reflects on friction points |
| **Beliefs Tracking** | None | Claims and contradictions tracked across pipeline |

## Feature Comparison

### Old Experiment Generated:
- ✅ Basic function implementation
- ✅ Type hints via ftl-doc-agent3
- ✅ Google-style docstrings via ftl-doc-agent
- ✅ Pytest tests via ftl-pytest-agent2
- ✅ Coverage reports
- ⚠️ No planning phase
- ⚠️ No code review
- ⚠️ No actual usage verification
- ⚠️ No error handling
- ⚠️ No iterative improvement

### Multiagent-Loop Generated:
- ✅ Comprehensive planning document (PLAN.md)
- ✅ Implementation with type hints AND docstrings
- ✅ **Input validation and error handling**
- ✅ **Code review with feedback** (REVIEW.md)
- ✅ **13 comprehensive test cases** (base, edge, invalid inputs, math properties)
- ✅ **Actual code execution and usage verification**
- ✅ **Usage guide with examples** (USAGE.md)
- ✅ **User feedback and feature requests** (USER_FEEDBACK.md)
- ✅ **Complete audit trail** (git log shows every stage)
- ✅ **Self-review from every agent**
- ✅ **Beliefs system tracking claims**
- ✅ **Iterative improvement capability**

## File Comparison

### Old Experiment (two-sum example):
```
two-sum/
├── two-sum.py          # Original code
├── two-sum.txt         # Problem description + solution
├── code.py             # Basic version
├── code2.py            # + type hints
├── code3.py            # + docstrings
├── code3.py,cover      # Coverage annotation
├── test_twoSum.py      # Auto-generated tests
├── test_twoSum.txt     # Test output
├── output.txt          # Processing log
├── run.sh              # Pipeline script
├── .coverage           # Coverage data
├── coverage_total.txt  # "89"
└── function_name.txt   # "twoSum"
```

### Multiagent-Loop (climbing-stairs):
```
leetcode/
├── TASK.md                        # Original task
├── PLAN.md                        # Planner's comprehensive plan
├── IMPLEMENTATION.md              # Implementer's notes + self-review
├── REVIEW.md                      # Reviewer's detailed feedback
├── USAGE.md                       # Tester's usage guide
├── USER_FEEDBACK.md               # User's actual usage report
├── ITERATION_1_UNDERSTANDING.md   # Cumulative understanding
├── ITERATION_1_HUMAN_REVIEW.md    # Ready for human review
├── FINAL_REPORT.md                # Complete summary
├── beliefs.md                     # Claim tracking
├── implementer/
│   ├── climbing_stairs.py         # Production-ready code
│   └── test_climbing_stairs.py    # 13 comprehensive tests
├── tester/
│   ├── TEST_REPORT.md             # Test results
│   ├── USAGE_GUIDE.md             # Detailed usage docs
│   └── manual_test.py             # Manual verification
├── user/
│   └── test_usage.py              # Real usage examples
├── entries/iteration-1/           # Full audit trail
│   ├── planner.md
│   ├── implementer.md
│   ├── reviewer.md
│   ├── tester.md
│   └── user.md
└── .git/                          # Full version control
```

## Code Quality Comparison

### Old Experiment (two-sum/code3.py):
```python
from typing import List

def twoSum(nums: List[int], target: int) -> List[int]:
    """
    Finds two distinct indices in the list such that their corresponding values sum to the target.

    Args:
        nums: A list of integers.
            Each element represents a number in integer format.
        target: The desired sum of two numbers from the list, specified as an integer.

    Returns:
        List[int]: Two integers representing zero-based indices of the elements whose sum equals the target.
    """
    map = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in map:
            return [map[complement], i]
        map[num] = i
    return []
```

**Observations:**
- ✅ Type hints present
- ✅ Good docstring
- ⚠️ No input validation
- ⚠️ No error handling
- ⚠️ Returns empty list on failure (not explicit)

### Multiagent-Loop (implementer/climbing_stairs.py):
```python
def climbStairs(n: int) -> int:
    """Calculate the number of distinct ways to climb n stairs.

    Each time you can climb either 1 or 2 steps. This problem maps to the
    Fibonacci sequence where F(n) = F(n-1) + F(n-2), because to reach stair n,
    you can only arrive from stair n-1 (taking 1 step) or stair n-2 (taking 2 steps).

    This implementation uses an iterative dynamic programming approach with
    constant space optimization, tracking only the last two values instead of
    maintaining a full array.

    Args:
        n: The total number of stairs to climb. Must be between 1 and 45 inclusive.

    Returns:
        The number of distinct ways to climb to the top.

    Raises:
        ValueError: If n is not within the valid range [1, 45].

    Examples:
        >>> climbStairs(1)
        1
        >>> climbStairs(5)
        8

    Time Complexity:
        O(n) - Single pass through values from 1 to n.

    Space Complexity:
        O(1) - Only stores the previous two values.
    """
    # Input validation
    if not isinstance(n, int):
        raise ValueError(f"n must be an integer, got {type(n).__name__}")
    if n < 1 or n > 45:
        raise ValueError(f"n must be between 1 and 45 inclusive, got {n}")

    # Base cases
    if n == 1:
        return 1
    if n == 2:
        return 2

    # Iterative DP with O(1) space
    prev2 = 1
    prev1 = 2

    for i in range(3, n + 1):
        current = prev1 + prev2
        prev2 = prev1
        prev1 = current

    return prev1
```

**Observations:**
- ✅ Type hints present
- ✅ Comprehensive docstring with examples
- ✅ **Complexity analysis documented**
- ✅ **Mathematical explanation (Fibonacci connection)**
- ✅ **Input validation with type checking**
- ✅ **Range validation**
- ✅ **Clear error messages**
- ✅ **Explicit exception raising**

## Test Quality Comparison

### Old Experiment Tests (auto-generated):
- Basic assertions checking output equals target
- Typically 1-3 test cases
- No edge case coverage
- No invalid input testing

### Multiagent-Loop Tests:
- **13 comprehensive test cases**
- Base cases (n=1, n=2)
- Problem examples verification
- Small/medium/large values
- Maximum constraint (n=45)
- **Invalid input testing** (too small, too large, wrong type)
- **Mathematical property verification** (Fibonacci recurrence)
- **Sequential consistency checks**

## Verdict

The multiagent-loop represents a **massive improvement** over the old experiment:

1. **Quality**: Production-ready code with error handling and validation
2. **Completeness**: Full SDLC pipeline from planning to user acceptance
3. **Documentation**: Comprehensive guides at every stage
4. **Testing**: Thorough test coverage including edge cases
5. **Feedback**: Multiple review loops catch issues early
6. **Audit Trail**: Git commits provide full history
7. **Self-Improvement**: Agents identify friction points
8. **Iteration**: Can improve based on user feedback

The old experiment was a proof-of-concept for automated code generation.
The multiagent-loop is a **complete autonomous software development system**.
