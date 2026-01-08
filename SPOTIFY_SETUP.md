# Spotify Tracking Setup

This guide will help you set up Spotify playback tracking.

## Prerequisites

1. **Install required libraries**:
   ```bash
   conda activate apple-tv  # or your Python environment
   pip install spotipy python-dotenv
   ```

2. **Create a Spotify App** to get API credentials:
   - Go to https://developer.spotify.com/dashboard
   - Click "Create app"
   - Fill in:
     - **App name**: "Home Media Tracker" (or whatever you want)
     - **App description**: "Track my Spotify playback"
     - **Redirect URI**: `http://localhost:8888/callback`
     - **APIs used**: Check "Web API"
   - Click "Save"
   - You'll see your **Client ID** and **Client Secret**

## Configuration

Create a `.env` file in the project directory with your Spotify credentials:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use your favorite editor
```

Your `.env` file should look like:

```
SPOTIFY_CLIENT_ID=your_actual_client_id
SPOTIFY_CLIENT_SECRET=your_actual_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

**Note**: The `.env` file is gitignored and won't be committed to version control.

## First Run

Run the script manually first to authenticate:

```bash
python spotify_nowplaying.py
```

This will:
1. Open your browser for Spotify authentication
2. Ask you to authorize the app
3. Redirect back to localhost (you'll see a connection error - that's OK!)
4. Copy the full URL from your browser and paste it back into the terminal
5. Create a `.spotify_cache` file with your auth token

## Add to Cron

Once authentication works, add to your cron:

```bash
crontab -e
```

Add this line (adjust paths as needed):

```
*/3 * * * * cd /path/to/chatgptversion && source $HOME/mambaforge/etc/profile.d/conda.sh && conda activate apple-tv && python spotify_nowplaying.py >> cron.log 2>&1
```

## What Gets Tracked

The script captures:
- **Device name**: "Spotify: [Device Name]" (e.g., "Spotify: iPhone", "Spotify: Web Player")
- **Device type**: Computer, Smartphone, Speaker, TV, etc.
- **Track info**: Title, artist(s), album
- **Playback state**: Playing or Paused
- **Position**: Current playback position
- **Duration**: Track length
- **Media type**: Always "Music"

## Notes

- Runs independently from Apple TV tracking (no write conflicts)
- Uses the same database and table structure
- Only logs when something is actively playing or paused
- Skips repeated "Paused" states for the same track
- Auth token is cached in `.spotify_cache` (added to .gitignore)
