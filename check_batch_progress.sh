#!/bin/bash

echo "=== LeetCode Batch Progress ==="
echo "Time: $(date '+%H:%M:%S')"
echo

# Count completed workspaces
WORKSPACES=$(ls -1 ~/git/multiagent-loop/workspaces/ 2>/dev/null | grep -v "^iris$" | grep -v "^leetcode$")
COUNT=$(echo "$WORKSPACES" | grep -c '^')

echo "Completed workspaces: $COUNT/10"
echo

if [ -n "$WORKSPACES" ]; then
  echo "Problems processed:"
  echo "$WORKSPACES" | nl
  echo
fi

# Check if batch is still running
if ps aux | grep -q "[p]rocess_leetcode_batch.sh"; then
  echo "Status: ✓ Batch is running"
  
  # Check which agent is active
  if [ -f ~/git/multiagent-loop/pids/planner.pid ]; then
    echo "Current: Planner agent"
  elif [ -f ~/git/multiagent-loop/pids/implementer.pid ]; then
    echo "Current: Implementer agent"
  elif [ -f ~/git/multiagent-loop/pids/reviewer.pid ]; then
    echo "Current: Reviewer agent"
  elif [ -f ~/git/multiagent-loop/pids/tester.pid ]; then
    echo "Current: Tester agent"
  elif [ -f ~/git/multiagent-loop/pids/user.pid ]; then
    echo "Current: User agent"
  fi
else
  echo "Status: ✗ Batch completed or stopped"
fi

echo
echo "Latest log entries:"
tail -5 ~/git/multiagent-loop/multiagent.log 2>/dev/null | grep -E "\[INFO\]" | tail -3
