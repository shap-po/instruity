# Instruity

Custom made discord music bot made for me and my friends.
This bot is meant to be hosted on a Heroku server.

## Features

- Play music from YouTube (`/play <url | name>`)
- Use slash commands to control the bot
- Has a nice button interface to control the bot (`/actions`)
- You can run multiple instances of the bot on the same server
- Assign a "special" song to a bot via `SPECIALITIES` environment variable to play it via `/perform` command

## Setup

### Create a bot

1. Go to the (Discord Developer Portal)[https://discord.com/developers/applications]
1. Create a new application
1. Go to the "Bot" tab and click "Add Bot"
1. Copy the token and save it for later
1. Go to the "OAuth2" tab and select "bot" and "applications.commands" in the scopes section
1. Select the permissions the bot will need ("Send Messages", "Connect", "Speak" and "Read Messages/View Channels")
1. Copy the link, it will be used to invite the bot to a server

### Deploy the bot

#### Heroku

1. Create a new app on (Heroku)[https://dashboard.heroku.com/new-app]
1. Make sure to use `heroku-20` stack, as later versions have issues with ffmpeg at the time of writing
1. Add the following buildpacks (Settings -> Buildpacks -> Add buildpack):
   - `heroku/nodejs`
   - `heroku/python`
   - `https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest.git`
   - `https://github.com/xrisk/heroku-opus.git`
1. Add the following config vars (Settings -> Config Vars):
    - `TOKENS` - Tokens for the bots separated by any whitespace character (e.g. `token1 token2 ...`)
1. Connect the app to the repository (Deploy -> Deployment method -> GitHub)
1. Start the worker (Resources -> worker -> edit -> toggle the switch)

#### Local

1. Clone the repository
1. Install (ffmpeg)[https://www.ffmpeg.org/download.html]
1. Install (Python 3.10+)[https://www.python.org/downloads/]
1. Run the following commands:
    Windows:
    ```cmd
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    ```

    Linux:
    ```bash
        python -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
        ```
1. Create a `.env` file with the following content:
   ```env
   TOKENS=token1\ntoken2
   ```
1. Run the bot with the following command:
    Windows:
        ```cmd
        .venv\Scripts\python bot.py
        ```

    Linux:
        ```bash
        .venv/bin/python bot.py
        ```
