# Spotify Tracking Setup

This guide will help you set up Spotify playback tracking for single or multiple users (e.g., family members).

## Prerequisites

1. **Install required libraries**:
   ```bash
   conda activate apple-tv  # or your Python environment
   pip install spotipy python-dotenv
   ```

2. **Create ONE Spotify App** to get API credentials:
   
   - Go to https://developer.spotify.com/dashboard
   - Log in with any Spotify account (doesn't matter whose)
   - Click "Create app"
   - Fill in:
     - **App name**: "Home Media Tracker" (or whatever you want)
     - **App description**: "Track family Spotify playback"
     - **Redirect URI**: `http://127.0.0.1:8888/callback`
     - **APIs used**: Check "Web API"
   - Click "Save"
   - Copy the **Client ID** and **Client Secret**
   
3. **Add Family Members to App** (if tracking multiple users):
   
   - In the app dashboard, click on the app you just created
   - Go to "User Management" in the left sidebar
   - Click "Add User"
   - Enter each family member's Spotify email address
   - Each person will receive an invitation email to authorize the app
   - **Note**: This step is only needed during development. Once you submit the app for quota extension, you won't need this.

## Configuration

Create a `.env` file in the project directory with your Spotify credentials:

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your credentials
nano .env  # or use your favorite editor
```

### For Multiple Users (Recommended)

Use **one app** with multiple user names:

```
SPOTIFY_CLIENT_ID=your_actual_client_id
SPOTIFY_CLIENT_SECRET=your_actual_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
SPOTIFY_USERS=Mom,Dad,Kid
```

The `SPOTIFY_USERS` variable is a comma-separated list of user names. Each person will authenticate with their own Spotify account when they first run the script.

### For Single User

Just omit the `SPOTIFY_USERS` variable:

```
SPOTIFY_CLIENT_ID=your_actual_client_id
SPOTIFY_CLIENT_SECRET=your_actual_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
```

**Note**: The `.env` file is gitignored and won't be committed to version control.

## First Run - Authentication

Each user needs to authenticate once with their Spotify account. Run the script manually first:

```bash
python spotify_nowplaying.py
```

### For Multiple Users

The script will authenticate each user **one at a time**:

1. **User 1 authentication** (e.g., Mom):
   - Browser opens automatically
   - **Log in with that user's Spotify account**
   - Click "Agree" to authorize the app
   - Browser redirects to localhost (shows connection error - that's OK!)
   - Copy the full URL from browser address bar
   - Paste URL into terminal
   - Creates `.spotify_cache_mom` file

2. **User 2 authentication** (e.g., Dad):
   - Browser opens for second user
   - **Important**: Make sure to log in with the **correct Spotify account**
   - If browser is still logged in as User 1, log out first or use incognito mode!
   - Click "Agree" and copy/paste the redirect URL
   - Creates `.spotify_cache_dad` file

3. Repeat for each user in your `SPOTIFY_USERS` list

**Tips**:
- Use different browser profiles or incognito windows to avoid mixing up accounts
- Each user only needs to authenticate once - tokens are cached
- Make sure each family member has been added in "User Management" in the Spotify app dashboard

### For Single User

Same process, but only one authentication needed:

1. Browser opens for Spotify login
2. Authorize the app
3. Copy/paste the redirect URL from browser
4. Creates `.spotify_cache` file

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
