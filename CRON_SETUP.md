# Automated Session Analysis Setup

This guide explains how to set up automated session analysis that runs every 12 hours.

## Overview

The `run_session_analysis.sh` script automatically:
- Activates the correct conda environment
- Runs the enriched session analysis
- Logs output to timestamped files
- Keeps only the last 30 log files to prevent disk space issues

## Setup Instructions

### 1. Verify the Script Works

First, test the script manually to ensure it runs correctly:

```bash
cd /Users/tfoss/code/appletv_poker/chatgptversion
./run_session_analysis.sh
```

You should see the session analysis output and a new log file created in the `logs/` directory.

### 2. Add to Crontab

Open your crontab for editing:

```bash
crontab -e
```

Add the following line to run the analysis every 12 hours (at midnight and noon):

```bash
0 */12 * * * /Users/tfoss/code/appletv_poker/chatgptversion/run_session_analysis.sh
```

Or for specific times (e.g., 8am and 8pm daily):

```bash
0 8,20 * * * /Users/tfoss/code/appletv_poker/chatgptversion/run_session_analysis.sh
```

Save and exit (in vi/vim: press `Esc`, then type `:wq` and press Enter).

### 3. Verify Crontab Entry

Check that your crontab was updated correctly:

```bash
crontab -l
```

You should see your new entry listed.

## Understanding the Schedule Format

The cron schedule format is: `minute hour day month weekday command`

Examples:
- `0 */12 * * *` - Every 12 hours (midnight and noon)
- `0 8,20 * * *` - Daily at 8am and 8pm
- `0 0 * * *` - Daily at midnight
- `0 */6 * * *` - Every 6 hours
- `*/30 * * * *` - Every 30 minutes

## Log Files

Log files are stored in the `logs/` directory with timestamps:
- Location: `/Users/tfoss/code/appletv_poker/chatgptversion/logs/`
- Format: `session_analysis_YYYYMMDD_HHMMSS.log`
- Retention: Last 30 files are kept, older ones are automatically deleted

To view the most recent log:

```bash
cd /Users/tfoss/code/appletv_poker/chatgptversion/logs
ls -t session_analysis_*.log | head -1 | xargs cat
```

To view logs in real-time (if you run manually):

```bash
tail -f logs/session_analysis_*.log
```

## Output Database

The script updates the `viewing_sessions` table in `atv_usage.duckdb` with:
- Session groupings (same media on same device within 10-minute gaps)
- Start/end times for each session
- Watch time and completion percentages
- Device, app, and user information

You can query this table directly using DuckDB:

```bash
python3 -c "import duckdb; con = duckdb.connect('atv_usage.duckdb'); print(con.sql('SELECT * FROM viewing_sessions ORDER BY session_start DESC LIMIT 10'))"
```

## Troubleshooting

### Check if cron is running:

```bash
ps aux | grep cron
```

### View cron system log (macOS):

```bash
log show --predicate 'process == "cron"' --last 1h
```

### Test the conda environment manually:

```bash
eval "$($HOME/mambaforge/bin/conda shell.bash hook)"
conda activate apple-tv
python -c "import duckdb; print('Success!')"
```

### Common Issues

1. **Script not executing**: Ensure the script has execute permissions:
   ```bash
   chmod +x /Users/tfoss/code/appletv_poker/chatgptversion/run_session_analysis.sh
   ```

2. **Conda not found**: Verify the mambaforge path in the script matches your installation:
   ```bash
   ls -la $HOME/mambaforge/bin/conda
   ```

3. **Database locked**: The cron job and manual data collection scripts can't run simultaneously. If you see "database is locked" errors, wait for the other process to complete.

## Modifying the Schedule

To change the schedule, edit your crontab again:

```bash
crontab -e
```

Modify the timing values and save. Changes take effect immediately.

## Removing the Cron Job

To stop automated analysis:

```bash
crontab -e
```

Delete the line or comment it out by adding `#` at the beginning, then save.
