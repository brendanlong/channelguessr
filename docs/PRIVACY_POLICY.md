# Privacy Policy

**Last Updated: January 24, 2026**

## Overview

Channelguessr is a Discord bot game. This policy explains what data we collect and how we use it.

## Data We Collect

We store the following data in a SQLite database:

### Game Data
- **Discord IDs**: Server (guild) IDs, channel IDs, message IDs, and user IDs
- **Game rounds**: Which messages were selected for games and when
- **Player guesses**: Your guesses during gameplay
- **Scores**: Points earned and rounds played per server

### What We Do NOT Store
- Message content (we only store message IDs)
- Usernames or display names
- Any personal information beyond Discord IDs

## How We Use Your Data

Your data is used solely to:
- Run the game (tracking rounds, scores, and leaderboards)
- Debug issues if something goes wrong

We do not:
- Sell your data
- Share your data with third parties
- Use your data for advertising or analytics
- Use your data for any purpose other than running this game

## Data Storage

Data is stored in a SQLite database hosted on [Fly.io](https://fly.io) infrastructure in the United States.

## Data Retention

Game data is retained while the bot is in your server.

## Data Deletion

**Self-service:** Use the `/cleardata` command to delete all your personal data from all servers. This removes your guesses and leaderboard scores permanently.

**Automatic deletion:** When the bot is removed from a server, all data for that server is automatically and permanently deleted. This includes all game rounds, player guesses, and leaderboard scores.

**Manual requests:** Server administrators can also request data deletion at any time by opening an issue on the [GitHub repository](https://github.com/brendanlong/channelguessr).

## Third-Party Services

- **Discord**: The bot operates through Discord's API. Discord's privacy policy applies to your use of Discord.
- **Fly.io**: Our hosting provider. See [Fly.io's privacy policy](https://fly.io/legal/privacy-policy/).

## Children's Privacy

This bot is not intended for children under 13. We do not knowingly collect data from children under 13.

## Changes to This Policy

We may update this policy at any time. Changes will be reflected in the "Last Updated" date.

## Contact

For privacy questions or data deletion requests, open an issue on the [GitHub repository](https://github.com/brendanlong/channelguessr).
