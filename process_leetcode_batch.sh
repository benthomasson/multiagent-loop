#!/bin/bash
set -e

# List of LeetCode problems to process
PROBLEMS=(
  "fibonacci-number"
  "is-subsequence"
  "to-lower-case"
  "merge-sorted-array"
  "sqrtx"
  "reverse-string"
  "single-number"
  "plus-one"
  "add-binary"
  "contains-duplicate"
)

LEETCODE_DIR="$HOME/data/leetcode/leetcode"
MULTIAGENT_DIR="$HOME/git/multiagent-loop"

cd "$MULTIAGENT_DIR"

echo "========================================="
echo "Processing ${#PROBLEMS[@]} LeetCode Problems"
echo "Effort Level: MINIMAL (fast execution)"
echo "========================================="
echo

for problem in "${PROBLEMS[@]}"; do
  echo "========================================="
  echo "Problem: $problem"
  echo "========================================="
  
  # Check if problem directory exists
  if [ ! -d "$LEETCODE_DIR/$problem" ]; then
    echo "ERROR: Problem directory not found: $LEETCODE_DIR/$problem"
    echo "Skipping..."
    echo
    continue
  fi
  
  # Read problem description from prompt.txt or {problem}.txt
  PROBLEM_FILE=""
  if [ -f "$LEETCODE_DIR/$problem/prompt.txt" ]; then
    PROBLEM_FILE="$LEETCODE_DIR/$problem/prompt.txt"
  elif [ -f "$LEETCODE_DIR/$problem/${problem}.txt" ]; then
    PROBLEM_FILE="$LEETCODE_DIR/$problem/${problem}.txt"
  else
    echo "ERROR: No problem description found"
    echo "Skipping..."
    echo
    continue
  fi
  
  echo "Reading problem from: $PROBLEM_FILE"
  
  # Read function name if available
  FUNCTION_NAME=""
  if [ -f "$LEETCODE_DIR/$problem/function_name.txt" ]; then
    FUNCTION_NAME=$(cat "$LEETCODE_DIR/$problem/function_name.txt")
    echo "Function name: $FUNCTION_NAME"
  fi
  
  # Build task description
  TASK="Solve the LeetCode problem from $problem:

$(cat "$PROBLEM_FILE")

Requirements:
- Implement the solution with proper type hints
- Add comprehensive Google-style docstring
- Include input validation and error handling
- Create thorough unit tests covering edge cases
- Optimize for time and space complexity"

  if [ -n "$FUNCTION_NAME" ]; then
    TASK="$TASK
- Function name should be: $FUNCTION_NAME"
  fi
  
  echo
  echo "Starting multiagent-loop for $problem..."
  echo "Workspace: $problem"
  echo
  
  # Run the supervisor with minimal effort for fast execution
  uv run supervisor.py \
    --workspace "$problem" \
    --effort minimal \
    "$TASK"
  
  EXIT_CODE=$?
  
  if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Successfully completed: $problem"
  else
    echo "✗ Failed: $problem (exit code: $EXIT_CODE)"
  fi
  
  echo
  echo "Results saved to: workspaces/$problem/"
  echo
  echo "========================================="
  echo
  
  # Brief pause between problems
  sleep 2
done

echo
echo "========================================="
echo "Batch Processing Complete!"
echo "========================================="
echo
echo "Results:"
for problem in "${PROBLEMS[@]}"; do
  if [ -d "workspaces/$problem" ]; then
    echo "✓ $problem - workspaces/$problem/"
  else
    echo "✗ $problem - not processed"
  fi
done
