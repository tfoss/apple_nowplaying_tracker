#!/bin/bash
# Cronjob-runnable script to run session analysis every 12 hours
# Add to crontab with: 0 */12 * * * /path/to/run_session_analysis.sh

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory if it doesn't exist
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# Set up log file with timestamp
LOG_FILE="$LOG_DIR/session_analysis_$(date +%Y%m%d_%H%M%S).log"

# Redirect all output to log file
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "========================================"
echo "Session Analysis Run: $(date)"
echo "========================================"
echo ""

# Clear inherited conda variables to prevent errors
unset CONDA_SHLVL CONDA_DEFAULT_ENV CONDA_PREFIX CONDA_PROMPT_MODIFIER

# Initialize conda for bash/sh
eval "$($HOME/mambaforge/bin/conda shell.bash hook)"
conda activate apple-tv

python "$SCRIPT_DIR/analyze_sessions_enriched.py"
EXIT_CODE=$?

echo ""
echo "========================================"
echo "Analysis completed with exit code: $EXIT_CODE"
echo "Finished at: $(date)"
echo "========================================"

# Keep only the last 30 log files
cd "$LOG_DIR"
ls -t session_analysis_*.log | tail -n +31 | xargs rm -f 2>/dev/null

exit $EXIT_CODE
