# DevLog Multi-Platform Publisher

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An intelligent automation bot that monitors RSS feeds for game development updates and automatically publishes them across multiple social media platforms with rich content formatting and media support.

## 🚀 Features

### Smart Content Processing
- **Hybrid RSS + Web Scraping**: Polls RSS feeds for new posts, then scrapes the full HTML content for complete devlog text
- **Intelligent Content Matching**: Uses fuzzy matching algorithms to identify and extract the actual devlog content from web pages
- **Image Extraction**: Automatically finds and extracts relevant images from both RSS feeds and scraped web pages
- **Gallery Support**: Special handling for itch.io gallery images with preference for high-resolution originals

### Multi-Platform Publishing
- **Discord**: Rich embeds with full scraped content, multiple images, and formatted text
- **Twitter**: Character-optimized posts with first paragraph, media uploads (up to 4 images)
- **BlueSky**: Native posts with image embeds and link previews

### Platform-Specific Optimizations
- **Discord**: Uses full scraped content with markdown formatting, multiple embeds for additional images
- **Twitter/BlueSky**: Uses first paragraph only with markdown stripped for clean social media posts
- **Intelligent Truncation**: Content is truncated at sentence/paragraph boundaries for natural cutoffs

### Robust Architecture
- **Async/Await**: Fully asynchronous for efficient operation
- **Per-Platform Tracking**: SQLite database tracks posting status independently for each platform
- **Rate Limit Handling**: Built-in delays and retry logic to respect API limits
- **Comprehensive Logging**: Detailed logging for monitoring and debugging

---

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup Instructions

1. **Clone the repository:**
```bash
git clone https://github.com/Aadiwrth/devlog-Multi-Platform-Publisher.git
cd devlog-Multi-Platform-Publisher
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Create environment file:**
```bash
cp .env.example .env
```

4. **Configure your credentials in `.env`:**
```env
# RSS Feed Configuration
RSS_URL=https://yourgame.itch.io/devlog.rss

# Discord Configuration
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_channel_id

# Twitter Configuration
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# BlueSky Configuration
BLUESKY_HANDLE=yourhandle.bsky.social
BLUESKY_PASSWORD=your_app_password

# Bot Configuration
RUN_ONCE=false
CHECK_INTERVAL_MINUTES=30
```

---

## ⚙️ Platform Configuration

### Discord Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Navigate to "Bot" section and click "Add Bot"
4. Enable **"Message Content Intent"** under Privileged Gateway Intents
5. Copy the bot token
6. Generate an invite URL:
   - Go to OAuth2 → URL Generator
   - Select scopes: `bot`
   - Select permissions: `Send Messages`, `Embed Links`
7. Use the generated URL to invite the bot to your server
8. Right-click your target channel → Copy ID (enable Developer Mode in Settings)
9. Add token and channel ID to `.env`

### Twitter Setup

1. Apply for Twitter Developer access at [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a new app (Project & App)
3. Set app permissions to **"Read and Write"**
4. Generate API Key and Secret
5. Generate Access Token and Secret
6. Add all four credentials to `.env`

### BlueSky Setup

1. Create a BlueSky account at [bsky.app](https://bsky.app)
2. Go to Settings → App Passwords
3. Generate a new app password
4. Add your handle (e.g., `yourname.bsky.social`) and app password to `.env`

---

## 🎮 Usage

### Run Continuously (Daemon Mode)
Monitor RSS feed and post updates at regular intervals:
```bash
python main.py
```

The bot will check for new posts every 30 minutes by default (configurable via `CHECK_INTERVAL_MINUTES`).

### Run Once (Single Execution)
Process current feed entries and exit:
```bash
RUN_ONCE=true python main.py
```

Or permanently set `RUN_ONCE=true` in your `.env` file.

### Custom Check Interval
Adjust the monitoring frequency (in minutes):
```bash
CHECK_INTERVAL_MINUTES=60 python main.py
```

---

## 📁 Project Structure

```
devlog-Multi-Platform-Publisher/
│
├── main.py                 # Main bot orchestration and entry point
├── rss_parser.py          # RSS parsing and web scraping logic
├── discord_poster.py      # Discord integration module
├── twitter_poster.py      # Twitter/X integration module
├── bluesky_poster.py      # BlueSky integration module
├── database.py            # SQLite database management
│
├── .env           # Example environment variables
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── devlog_posts.db        # SQLite database (auto-generated)
```

---

## 🔧 Dependencies

```txt
feedparser>=6.0.10         # RSS feed parsing
beautifulsoup4>=4.11.1     # HTML parsing and scraping
requests>=2.28.0           # HTTP requests
aiohttp>=3.8.3             # Async HTTP client
discord.py>=2.1.0          # Discord API wrapper
tweepy>=4.12.0             # Twitter API wrapper
python-dotenv>=0.21.0      # Environment variable management
```

Install all dependencies:
```bash
pip install -r requirements.txt
```

---

## 🔍 How It Works

### Content Processing Pipeline

```
┌─────────────────┐
│   RSS Feed      │
│   Monitoring    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Detect New     │
│  Entries        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Web Scraping   │
│  (Full Content) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Content        │
│  Matching       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Image          │
│  Extraction     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Platform       │
│  Publishing     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Database       │
│  Tracking       │
└─────────────────┘
```

### Detailed Flow

1. **RSS Polling**: Bot periodically checks the RSS feed for new entries
2. **Content Detection**: Identifies posts not yet processed for each platform
3. **Web Scraping**: Fetches the full HTML page for each new post
4. **Smart Matching**: Uses fuzzy text matching to locate the actual devlog content
5. **Image Extraction**: 
   - Finds gallery images in `post_images` sections
   - Extracts inline images from matched content
   - Prioritizes high-resolution originals over thumbnails
6. **Platform-Specific Formatting**:
   - Discord: Full markdown-formatted content
   - Twitter: First paragraph, stripped of markdown
   - BlueSky: First paragraph with link preview
7. **Publishing**: Posts to all configured platforms asynchronously
8. **Database Tracking**: Records successful posts per-platform to prevent duplicates

---

## 🎯 Platform-Specific Features

### Discord
- **Rich Embeds**: Full content with markdown formatting
- **Multiple Images**: Main embed + additional image embeds (up to 4 total)
- **Continuation Messages**: Splits very long content across multiple embeds
- **Custom Footer**: Timestamp and custom icon

### Twitter
- **Character Optimization**: Smart truncation at sentence boundaries
- **Media Uploads**: Up to 4 images per tweet
- **Clean Text**: Markdown stripped for social media readability
- **Rate Limit Handling**: Automatic retry with exponential backoff

### BlueSky
- **Native Images**: Direct image uploads (up to 4 per post)
- **Link Previews**: Automatic metadata extraction
- **Session Management**: Automatic authentication refresh
- **App Password Support**: Secure authentication method

---

## 🐛 Troubleshooting

### Bot Not Posting

**Issue**: No posts appearing on platforms

**Solutions**:
```bash
# Check credentials
cat .env | grep TOKEN

# Verify RSS feed is accessible
curl -I https://yourgame.itch.io/devlog.rss

# Check logs for errors
python main.py 2>&1 | tee bot.log

# Test individual platform connections
python -c "from discord_poster import DiscordPoster; ..."
```

### Images Not Appearing

**Issue**: Posts succeed but images missing

**Causes & Solutions**:
- **Size Limits**: Twitter (5MB), BlueSky (1MB) - compress images
- **URL Accessibility**: Ensure images are publicly accessible
- **Content Type**: Must be valid image formats (PNG, JPG, GIF, WEBP)
- **Network Issues**: Check firewall/proxy settings

```python
# Check image accessibility
import requests
response = requests.head('https://your-image-url.jpg')
print(f"Status: {response.status_code}")
print(f"Size: {response.headers.get('Content-Length')} bytes")
print(f"Type: {response.headers.get('Content-Type')}")
```

### Content Truncation

**Issue**: Posts are cut off

**Explanation**: This is normal behavior due to platform limits:
- Twitter: 280 characters
- BlueSky: 300 characters  
- Discord: 4096 characters per embed (splits into multiple embeds if needed)

**Customize truncation**:
```python
# In twitter_poster.py or bluesky_poster.py
def _format_post_text(self, post, max_length=280):
    # Adjust max_length as needed
```

### Database Issues

**Issue**: Posts being reposted or database errors

**Solutions**:
```bash
# Reset database
rm devlog_posts.db
python main.py  # Will recreate database

# Check database contents
sqlite3 devlog_posts.db "SELECT * FROM posted_entries;"

# Verify table structure
sqlite3 devlog_posts.db ".schema posted_entries"
```

### Rate Limiting

**Issue**: "Rate limit exceeded" errors

**Solutions**:
```python
# Increase delays in main.py
await asyncio.sleep(5)  # Between posts

# Reduce check frequency
CHECK_INTERVAL_MINUTES=60  # In .env

# For Twitter: wait_on_rate_limit=True is already enabled
```

---

## 🔐 Security Best Practices


1. **Use app passwords**: For BlueSky, use app-specific passwords
2. **Rotate credentials**: Regularly update API keys and tokens
3. **Limit permissions**: Give bot only required permissions
4. **Monitor logs**: Check for unauthorized access attempts

```bash
# Check if .env is tracked
git status | grep .env

# If accidentally committed
git rm --cached .env
git commit -m "Remove .env from tracking"
```

---

## 🤝 Contributing

Contributions are welcome! Here's how to contribute:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit changes**: `git commit -m 'Add amazing feature'`
4. **Push to branch**: `git push origin feature/amazing-feature`
5. **Open a Pull Request**

### Development Setup
```bash
# Clone your fork
git clone https://github.com/Aadiwrth/devlog-Multi-Platform-Publisher.git

# Add upstream remote
git remote add upstream https://github.com/Aadiwrth/devlog-Multi-Platform-Publisher.git

# Create development branch
git checkout -b dev
```

### Code Style
- Follow PEP 8 guidelines
- Use meaningful variable names
- Add docstrings to functions
- Update README for new features

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2024 Aadiwrth

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## 🙏 Acknowledgments

- Built for indie game developers sharing devlogs on **itch.io**
- Supports Discord communities, Twitter followers, and BlueSky users
- Designed to handle itch.io's specific HTML structure but adaptable to other platforms
- Special thanks to the BeautifulSoup and feedparser communities

---

## 📊 Example Output

### Discord Post
```
┌─────────────────────────────────────┐
│  New Character System Update      │
├─────────────────────────────────────┤
│ ### Character Customization         │
│                                     │
│ We've implemented a new character   │
│ customization system that allows    │
│ players to modify their avatars...  │
│                                     │
│ • Hair styles: 15 options           │
│ • Color palettes: RGB support       │
│ • Equipment slots: 8 total          │
│                                     │
│ [Embedded Images: 3]                │
├─────────────────────────────────────┤
│ 📅 New Devlog • Oct 1, 2025        │
└─────────────────────────────────────┘
```

### Twitter Post
```
New Character System Update

We've implemented a new character customization 
system that allows players to modify their avatars 
with 15 hair styles and RGB color support...

https://yourgame.itch.io/devlog/123

[4 images attached]
```

### BlueSky Post
```
New Character System Update

We've implemented a new character customization 
system that allows players to modify their avatars 
with 15 hair styles and RGB color support...

Learn More => https://yourgame.itch.io/devlog/123

[4 images embedded]
```

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Aadiwrth/devlog-Multi-Platform-Publisher/issues)
- **Email**: Create an issue for support requests

---

## 🗺️ Roadmap

- [ ] Add support for Mastodon
- [ ] Implement Instagram posting
- [ ] Add webhook support for real-time notifications
- [ ] Create web dashboard for monitoring
- [ ] Add support for video content
- [ ] Implement A/B testing for post formats
- [ ] Add analytics and engagement tracking

---

## ⭐ Star History

If you find this project useful, please consider giving it a star on GitHub!

[![Star History Chart](https://api.star-history.com/svg?repos=Aadiwrth/devlog-Multi-Platform-Publisher&type=Date)](https://star-history.com/#Aadiwrth/devlog-Multi-Platform-Publisher&Date)

---

**Made with ❤️ by indie devs, for indie devs**