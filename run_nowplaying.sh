#!/bin/bash
# Adjust this path if your conda is installed elsewhere
source "$HOME/mambaforge/etc/profile.d/conda.sh"
conda activate apple-tv

python "$HOME/code/appletv_poker/nowplaying_multi.py"
python "$HOME/code/appletv_poker/spotify_nowplaying.py"

echo "$(date) – cron ran" > "$HOME/code/appletv_poker/last_cron_run.txt"
