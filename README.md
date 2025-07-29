# FlipperBot

A powerful Discord bot for Hypixel Skyblock flipping with advanced features and server management capabilities.

## Features

### Core Features
- Automatic flip detection
- Real-time profit calculations
- Custom flip alerts
- User authentication
- Admin controls

### New Features
- **Button-Based Interaction System**
  - Automatic role assignment for new members
  - Customizable verification system
  - Interactive Q&A system
  - Configurable button styles and labels

- **Server Templates**
  - Pre-made server structures with `/template_use` command
  - Multiple template options:
    - 🏰 Dungeon Server
    - 🌾 Farming Server
    - 🌟 General Gaming Server
  - Beautiful channel organization with emojis
  - Proper permission setup

## Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/flipperbot.git
cd flipperbot
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure the bot
- Copy `config.example.yaml` to `config.yaml`
- Fill in your bot token and other required values
- Customize button labels and styles if desired

## Configuration

### Button Customization
```yaml
buttons:
  verify_label: "Verify"  # Custom label for verify button
  qa_label: "Q&A"  # Custom label for Q&A button
  verify_emoji: "✅"  # Custom emoji for verify button
  qa_emoji: "❓"  # Custom emoji for Q&A button
  verify_style: "green"  # Button style: green, blue, red, grey
  qa_style: "blurple"  # Button style: green, blue, red, grey
```

### Server Templates
Use `/template_use` command to create pre-configured server structures:

1. 🏰 Dungeon Server
   - Main announcements
   - Chatting channels
   - Dungeon-specific channels
   - Gaming coordination

2. 🌾 Farming Server
   - Main announcements
   - Chatting channels
   - Farming guides and tips
   - Competition tracking

3. 🌟 General Gaming Server
   - Main announcements
   - Community channels
   - Gaming coordination
   - Bot commands

## Environment Variables

Required environment variables:
- `BOT_TOKEN`: Your Discord bot token
- `OWNER_ID`: Your Discord user ID
- `HYPIXEL_API_KEY`: Your Hypixel API key
- `MS_CLIENT_ID`: Microsoft OAuth client ID
- `MS_CLIENT_SECRET`: Microsoft OAuth client secret
- `ADMIN_WEBHOOK`: Admin notifications webhook URL
- `NOTIFICATIONS_WEBHOOK`: General notifications webhook URL

## Commands

### Admin Commands
- `/template_use` - Apply a server template
- `/config` - Configure bot settings
- `/blacklist` - Manage blacklisted users
- `/whitelist` - Manage whitelisted users

### User Commands
- Verify button - Start verification process
- Q&A button - Access help and information

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, join our Discord server or open an issue on GitHub. 