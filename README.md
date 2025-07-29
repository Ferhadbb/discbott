# Hypixel Skyblock Flipper Bot

A Discord bot that monitors Hypixel Skyblock's auction house and bazaar for profitable flipping opportunities.

## Features

- Secure authentication methods:
  - Microsoft OAuth integration for seamless login
  - Manual login with OTP (Two-Factor Authentication) support
  - Encrypted credential storage
- Real-time monitoring of Hypixel Skyblock auctions
- Automatic flip detection based on customizable criteria
- Discord notifications for profitable opportunities
- Easy setup and configuration
- Detailed profit calculations and statistics

## Setup Instructions

1. Clone this repository
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up MongoDB:
   - Install MongoDB if not already installed
   - Start MongoDB service
   - Default connection URL: mongodb://localhost:27017/

4. Configure the bot:
   - Copy `config.example.yaml` to `config.yaml`
   - Edit `config.yaml` with your settings:
     ```yaml
     bot:
       token: "your_bot_token_here"
       # ... other bot settings
     
     access:
       owner_id: "your_discord_id_here"
       admin_ids:
         - "admin1_id_here"
       # ... other access settings
     
     channels:
       notifications:
         flip_alerts: "channel_id_here"
       # ... other channel settings
     ```

5. Get required API keys and credentials:
   - Discord Bot Token: Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
   - Hypixel API Key: Get it by connecting to Hypixel MC server and typing `/api new`
   - Microsoft OAuth credentials: Register an application at [Azure Portal](https://portal.azure.com)
     - Add `http://localhost:8000/callback` to the redirect URIs
     - Copy the client ID and generate a client secret

6. Run the bot:
   ```bash
   python bot.py
   ```

## Configuration Guide

The bot uses a YAML configuration file for all settings. The configuration is divided into several sections:

### Bot Configuration
```yaml
bot:
  token: "your_bot_token_here"  # Discord bot token
  prefix: "!"  # Command prefix
  status: "Watching for flips"  # Bot status
```

### Access Control
```yaml
access:
  owner_id: "your_discord_id_here"  # Bot owner
  admin_ids:  # Admin users
    - "admin1_id_here"
  whitelist_enabled: false  # Enable whitelist mode
```

### Channel Configuration
```yaml
channels:
  notifications:
    flip_alerts: "channel_id_here"  # Flip notifications
    announcements: "channel_id_here"  # Announcements
```

### Flip Settings
```yaml
flip_settings:
  check_interval: 30  # Seconds between checks
  min_profit: 100000  # Minimum profit (coins)
  min_profit_percentage: 20  # Minimum profit %
```

### Security Settings
```yaml
security:
  encryption_key: "auto_generated"  # For credential encryption
  require_2fa: true  # Require 2FA for manual login
```

See `config.example.yaml` for a complete list of configuration options with detailed comments.

## Authentication Commands

The bot supports two authentication methods:

### Microsoft OAuth Login
```
/login_microsoft
```
- Initiates Microsoft account login flow
- Sends you a link to authenticate with your Microsoft account
- Securely stores the OAuth tokens

### Manual Login with OTP
```
/login_manual
```
- Starts the manual login process
- Asks for your Minecraft email and password
- Sets up Two-Factor Authentication using any authenticator app
- Generates a QR code for easy OTP setup
- Securely stores your encrypted credentials

### Other Commands
```
/logout
```
- Removes your stored credentials from the bot

## Security Features

- All sensitive data is encrypted using Fernet symmetric encryption
- Credentials are stored securely in MongoDB
- OTP (Two-Factor Authentication) for additional security
- DM-only authentication commands
- Option to delete stored credentials at any time

## Contributing

Feel free to submit issues and enhancement requests!

## Security Note

- Never share your API keys, tokens, or credentials with anyone
- Keep your `config.yaml` file secure and never commit it to version control
- The bot will only ask for credentials through DM channels
- Always verify the bot's identity before entering sensitive information 