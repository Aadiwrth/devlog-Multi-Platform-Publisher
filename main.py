import asyncio
import logging
import os
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

from database import DatabaseManager
from rss_parser import RSSParser
from discord_poster import DiscordPoster
from twitter_poster import TwitterPoster
from bluesky_poster import BlueSkyPoster

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DevlogBot:
    def __init__(self):
        self.db = DatabaseManager()
        self.rss_parser = RSSParser(os.getenv('RSS_URL'))
        
        # Initialize social media posters
        self.posters = {}
        
        # Discord setup
        if os.getenv('DISCORD_BOT_TOKEN') and os.getenv('DISCORD_CHANNEL_ID'):
            self.posters['discord'] = DiscordPoster(
                os.getenv('DISCORD_BOT_TOKEN'),
                int(os.getenv('DISCORD_CHANNEL_ID'))
            )
        
        # Twitter setup
        if all([os.getenv('TWITTER_API_KEY'), os.getenv('TWITTER_API_SECRET'),
                os.getenv('TWITTER_ACCESS_TOKEN'), os.getenv('TWITTER_ACCESS_TOKEN_SECRET')]):
            self.posters['twitter'] = TwitterPoster(
                os.getenv('TWITTER_API_KEY'),
                os.getenv('TWITTER_API_SECRET'),
                os.getenv('TWITTER_ACCESS_TOKEN'),
                os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            )
        
        # BlueSky setup
        if os.getenv('BLUESKY_HANDLE') and os.getenv('BLUESKY_PASSWORD'):
            self.posters['bluesky'] = BlueSkyPoster(
                os.getenv('BLUESKY_HANDLE'),
                os.getenv('BLUESKY_PASSWORD')
            )
    
    async def process_new_posts(self):
        """Process new posts and post to all configured social media platforms"""
        logger.info("Starting to process new posts...")
        
        posts = self.rss_parser.parse_feed()
        if not posts:
            logger.info("No posts found in RSS feed")
            return
        
        logger.info(f"Found {len(posts)} posts in RSS feed")
        
        for post in posts:
            logger.info(f"Processing post: {post.title}")
            posted_status = self.db.is_post_processed(post.guid)
            
            # Process each configured platform
            for platform_name, poster in self.posters.items():
                if not posted_status.get(platform_name, False):
                    try:
                        logger.info(f"Attempting to post to {platform_name}: {post.title}")
                        success = await poster.post(post)
                        
                        if success:
                            self.db.mark_post_sent(post.guid, post.title, platform_name)
                            logger.info(f"Successfully posted to {platform_name}: {post.title}")
                        else:
                            logger.error(f"Failed to post to {platform_name}: {post.title}")
                    
                    except Exception as e:
                        logger.error(f"Error posting to {platform_name}: {e}")
                else:
                    logger.info(f"Post already sent to {platform_name}: {post.title}")
            
            # Add delay between posts to avoid rate limits
            await asyncio.sleep(2)
        
        logger.info("Finished processing all posts")
    
    async def run_once(self):
        """Run the bot once to process current posts"""
        await self.process_new_posts()
    
    async def run_periodically(self, interval_minutes: int = 30):
        """Run the bot periodically"""
        logger.info(f"Starting periodic monitoring every {interval_minutes} minutes")
        
        while True:
            try:
                await self.process_new_posts()
                logger.info(f"Waiting {interval_minutes} minutes until next check...")
                await asyncio.sleep(interval_minutes * 60)
            
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                logger.info("Continuing after error...")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    def get_configured_platforms(self) -> List[str]:
        """Get list of configured social media platforms"""
        return list(self.posters.keys())

async def main():
    """Main entry point"""
    bot = DevlogBot()
    
    configured_platforms = bot.get_configured_platforms()
    if not configured_platforms:
        logger.error("No social media platforms configured! Check your .env file.")
        return
    
    logger.info(f"Bot configured for platforms: {', '.join(configured_platforms)}")
    
    # Check if running in one-shot mode
    run_once = os.getenv('RUN_ONCE', 'false').lower() == 'true'
    
    if run_once:
        logger.info("Running in one-shot mode")
        await bot.run_once()
    else:
        interval = int(os.getenv('CHECK_INTERVAL_MINUTES', 600))
        await bot.run_periodically(interval)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")