# Spotify Tracking Setup

This guide will help you set up Spotify playback tracking for single or multiple users (e.g., family members).

## Prerequisites

1. **Install required libraries**:
   ```bash
   conda activate apple-tv  # or your Python environment
   pip install spotipy python-dotenv
   ```

2. **Create Spotify Apps** to get API credentials:
   
   **IMPORTANT**: Each family member needs their own Spotify App credentials. This is because:
   - Each user authenticates with their own Spotify account
   - Each user's credentials track only their listening activity
   - This allows you to see who is listening to what
   
   **For each user:**
   - Go to https://developer.spotify.com/dashboard
   - Log in with **that user's Spotify account** (or create apps under one account if preferred)
   - Click "Create app"
   - Fill in:
     - **App name**: "Home Media Tracker - [User Name]" (e.g., "Home Media Tracker - Mom")
     - **App description**: "Track my Spotify playback"
     - **Redirect URI**: `http://127.0.0.1:8888/callback`
     - **APIs used**: Check "Web API"
   - Click "Save"
   - Copy the **Client ID** and **Client Secret**
   - Repeat for each family member

## Configuration

Create a `.env` file in the project directory with your Spotify credentials:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use your favorite editor
```

### Option 1: Multiple Users (Family)

For tracking multiple family members:

```
SPOTIFY_USER_1_NAME=Mom
SPOTIFY_USER_1_CLIENT_ID=abc123...
SPOTIFY_USER_1_CLIENT_SECRET=xyz789...
SPOTIFY_USER_1_REDIRECT_URI=http://127.0.0.1:8888/callback

SPOTIFY_USER_2_NAME=Dad
SPOTIFY_USER_2_CLIENT_ID=def456...
SPOTIFY_USER_2_CLIENT_SECRET=uvw012...
SPOTIFY_USER_2_REDIRECT_URI=http://127.0.0.1:8888/callback

# Add more users as needed (USER_3, USER_4, etc.)
```

The script will track all configured users in a single run.

### Option 2: Single User

For tracking just one person (backwards compatible):

```
SPOTIFY_CLIENT_ID=your_actual_client_id
SPOTIFY_CLIENT_SECRET=your_actual_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

**Note**: The `.env` file is gitignored and won't be committed to version control.

## First Run - Authentication

### For Multiple Users

Each user needs to authenticate once. Run the script manually first:

```bash
python spotify_nowplaying.py
```

The script will authenticate each user **one at a time**:

1. **User 1 authentication**:
   - Browser opens for first user (e.g., Mom)
   - Log in with **that user's Spotify account**
   - Click "Agree" to authorize
   - Browser redirects to localhost (connection error - that's OK!)
   - Copy the full URL from browser address bar
   - Paste URL into terminal
   - Creates `.spotify_cache_mom` file (or whatever the user name is)

2. **User 2 authentication**:
   - Browser opens for second user (e.g., Dad)
   - **Important**: Make sure to log in with the **correct Spotify account** for this user
   - If the browser is still logged in as User 1, log out first!
   - Authorize and paste the redirect URL
   - Creates `.spotify_cache_dad` file

3. Repeat for each configured user

**Tip**: If users share a computer, use different browser profiles or incognito windows to avoid mixing up accounts during authentication.

### For Single User

Run the script manually first:

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
- **Device name**: "Spotify ([User Name]): [Device Name]" (e.g., "Spotify (Mom): iPhone", "Spotify (Dad): Web Player")
  - For single user mode: "Spotify (Default): [Device Name]"
- **Device type**: Computer, Smartphone, Speaker, TV, etc.
- **Track info**: Title, artist(s), album
- **Playback state**: Playing or Paused
- **Position**: Current playback position
- **Duration**: Track length
- **Media type**: Always "Music"

## Database Entries Example

With multiple users, entries look like:

```
device_name: Spotify (Mom): iPhone
device_name: Spotify (Dad): Desktop
device_name: Spotify (Kid): Web Player
```

This makes it easy to see who was listening to what in your viewing sessions analysis.

## Notes

- Runs independently from Apple TV tracking (no write conflicts)
- Uses the same database and table structure
- Only logs when something is actively playing or paused
- Skips repeated "Paused" states for the same track
- Auth tokens cached in `.spotify_cache_[username]` files (added to .gitignore)
- Each user's credentials track only that user's listening activity
- All users are polled in a single script run (every 3 minutes in cron)
