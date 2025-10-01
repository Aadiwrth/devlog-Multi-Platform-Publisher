import tweepy
import aiohttp
import asyncio
import logging
from typing import List
from io import BytesIO
from rss_parser import DevlogPost
import re

logger = logging.getLogger(__name__)

class TwitterPoster:
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        
        # Initialize Twitter API v2 client
        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
            wait_on_rate_limit=True
        )
        
        # Initialize Twitter API v1.1 for media upload
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        self.api_v1 = tweepy.API(auth)
    
    async def post(self, post: DevlogPost) -> bool:
        """Post content to Twitter"""
        try:
            # Prepare tweet text using full_content
            tweet_text = self._format_tweet_text(post)
            
            # Upload images if available
            media_ids = []
            if post.images:
                media_ids = await self._upload_images(post.images[:4])  # Twitter allows max 4 images
            
            # Post tweet
            if media_ids:
                response = self.client.create_tweet(text=tweet_text, media_ids=media_ids)
            else:
                response = self.client.create_tweet(text=tweet_text)
            
            if response.data:
                logger.info(f"Successfully posted to Twitter: {post.title}")
                return True
            else:
                logger.error(f"Failed to post to Twitter: {post.title}")
                return False
            
        except tweepy.TooManyRequests:
            logger.error("Twitter rate limit exceeded")
            return False
        except tweepy.Unauthorized:
            logger.error("Twitter authentication failed")
            return False
        except tweepy.Forbidden:
            logger.error("Twitter request forbidden - check permissions")
            return False
        except Exception as e:
            logger.error(f"Error posting to Twitter: {e}")
            return False
    
    def _extract_first_paragraph(self, content: str) -> str:
        """Extract only the first paragraph (up to first blank line)"""
        if not content:
            return ""
        
        # Split by double newline (blank line)
        paragraphs = content.split('\n\n')
        
        # Get first paragraph
        first_para = paragraphs[0].strip() if paragraphs else ""
        
        # Strip all markdown formatting
        first_para = self._strip_markdown_formatting(first_para)
        
        return first_para
    
    def _strip_markdown_formatting(self, text: str) -> str:
        """Remove all markdown formatting (bold, italic, etc.)"""
        if not text:
            return ""
        
        import re
        
        # Remove bold: **text** or __text__
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        
        # Remove italic: *text* or _text_
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        
        # Remove strikethrough: ~~text~~
        text = re.sub(r'~~(.+?)~~', r'\1', text)
        
        # Remove code: `text`
        text = re.sub(r'`(.+?)`', r'\1', text)
        
        # Remove headers: ### text
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        return text
        
    def _format_tweet_text(self, post: DevlogPost, max_length: int = 280) -> str:
        """Format post content for Twitter using full_content first paragraph"""
        title = post.title.strip()
        link_length = 23  # Twitter's t.co length
        
        # Get first paragraph from full_content
        content_source = post.full_content if hasattr(post, 'full_content') and post.full_content else post.content
        first_paragraph = self._extract_first_paragraph(content_source)
        
        # Calculate remaining space for content
        # Format: [title]\n\n[content]\n\n[link]
        buffer = 6  # for "\n\n" separators
        remaining_space = max_length - len(title) - link_length - buffer
        
        tweet_text = title
        
        if first_paragraph and remaining_space > 10:
            # Truncate first paragraph to fit
            content_preview = self._truncate_content(first_paragraph, remaining_space)
            tweet_text += f"\n\n{content_preview}"
        
        tweet_text += f"\n\n{post.link}"
        
        # Final safety check - trim if still too long
        if len(tweet_text) > max_length:
            logger.warning(f"Tweet text too long ({len(tweet_text)} chars), truncating to title + link only")
            tweet_text = f"{title}\n\n{post.link}"
        
        return tweet_text

    def _truncate_content(self, content: str, max_length: int) -> str:
        """Truncate content to specified length"""
        if len(content) <= max_length:
            return content

        # Try to truncate at sentence boundary
        sentences = content.split('. ')
        truncated = ""
        for sentence in sentences:
            if len(truncated + sentence + '. ') <= max_length - 3:
                truncated += sentence + '. '
            else:
                break
        if truncated:
            return truncated.rstrip() + "..."

        # If no sentence boundary fits, truncate at word boundary
        words = content.split()
        truncated = ""
        for word in words:
            if len(truncated + word + ' ') <= max_length - 3:
                truncated += word + ' '
            else:
                break
        return truncated.rstrip() + "..." if truncated else content[:max_length-3] + "..."
        
    async def _upload_images(self, image_urls: List[str]) -> List[str]:
        """Upload images to Twitter and return media IDs"""
        media_ids = []
        
        async with aiohttp.ClientSession() as session:
            for i, img_url in enumerate(image_urls):
                try:
                    logger.debug(f"Uploading image {i+1}/{len(image_urls)} to Twitter: {img_url}")
                    
                    # Download image
                    async with session.get(img_url, timeout=30) as response:
                        if response.status != 200:
                            logger.error(f"Failed to download image from {img_url}: HTTP {response.status}")
                            continue
                        
                        image_data = await response.read()
                        
                        if len(image_data) > 5 * 1024 * 1024:  # 5MB limit
                            logger.error(f"Image too large: {len(image_data)} bytes")
                            continue
                    
                    # Upload to Twitter
                    media = self.api_v1.media_upload(
                        filename=f"devlog_image_{i}.jpg",
                        file=BytesIO(image_data)
                    )
                    media_ids.append(media.media_id)
                    logger.debug(f"Successfully uploaded image {i+1} to Twitter")
                    
                    # Small delay between uploads
                    await asyncio.sleep(0.5)
                    
                except asyncio.TimeoutError:
                    logger.error(f"Timeout downloading image from {img_url}")
                    continue
                except Exception as e:
                    logger.error(f"Error uploading image to Twitter: {e}")
                    continue
        
        logger.info(f"Successfully uploaded {len(media_ids)} images to Twitter")
        return media_ids
    
    def test_connection(self) -> bool:
        """Test Twitter API connection"""
        try:
            # Test API connection by getting user info
            user = self.client.get_me()
            if user.data:
                logger.info(f"Twitter connection test successful for user: @{user.data.username}")
                return True
            else:
                logger.error("Twitter connection test failed: No user data")
                return False
        except Exception as e:
            logger.error(f"Twitter connection test failed: {e}")
            return False