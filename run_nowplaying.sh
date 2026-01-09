#!/bin/bash
# Adjust this path if your conda is installed elsewhere
source "$HOME/mambaforge/etc/profile.d/conda.sh"
conda activate apple-tv

python "$HOME/code/appletv_poker/chatgptversion/nowplaying_multi.py"
python "$HOME/code/appletv_poker/chatgptversion/spotify_nowplaying.py"

echo "$(date) – cron ran" > "$HOME/code/appletv_poker/chatgptversion/last_cron_run.txt"
