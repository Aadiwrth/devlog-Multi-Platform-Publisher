import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from rss_parser import DevlogPost
import io

logger = logging.getLogger(__name__)

class BlueSkyPoster:
    def __init__(self, handle: str, password: str):
        self.handle = handle
        self.password = password
        self.base_url = "https://bsky.social"
        self.session = None
        self.session_expires = None
    
    async def post(self, post: DevlogPost) -> bool:
        """Post content to BlueSky with images"""
        try:
            # Authenticate if needed
            if not await self._ensure_authenticated():
                logger.error("Authentication failed, cannot post")
                return False
            
            # Format post text using full_content
            post_text = self._format_post_text(post)
            
            # Create post record
            post_record = {
                "$type": "app.bsky.feed.post",
                "text": post_text,
                "createdAt": datetime.utcnow().isoformat() + "Z"
            }
            
            # Add images if available (BlueSky supports up to 4 images)
            if post.images:
                embed = await self._create_images_embed(post.images[:4])
                if embed:
                    post_record["embed"] = embed
                    logger.info(f"Added {len(post.images[:4])} images to BlueSky post")
            # Fallback to link embed if no images
            elif post.link:
                post_record["embed"] = await self._create_link_embed(post.link, post.title)
            
            # Create post
            post_data = {
                "repo": self.session["did"],
                "collection": "app.bsky.feed.post",
                "record": post_record
            }
            
            headers = {
                "Authorization": f"Bearer {self.session['accessJwt']}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/xrpc/com.atproto.repo.createRecord",
                    json=post_data,
                    headers=headers,
                    timeout=30
                ) as response:
                    
                    if response.status == 200:
                        logger.info(f"Successfully posted to BlueSky: {post.title}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"BlueSky post failed: HTTP {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error posting to BlueSky: {e}", exc_info=True)
            return False
    
    async def _create_images_embed(self, image_urls: List[str]) -> Optional[Dict]:
        """
        Create an images embed for BlueSky post.
        BlueSky supports up to 4 images per post.
        """
        try:
            uploaded_images = []
            
            for img_url in image_urls[:4]:  # Max 4 images
                blob = await self._upload_image(img_url)
                if blob:
                    uploaded_images.append({
                        "alt": "",  # You can add alt text if needed
                        "image": blob
                    })
                    logger.debug(f"Uploaded image: {img_url}")
            
            if not uploaded_images:
                logger.warning("No images were successfully uploaded")
                return None
            
            return {
                "$type": "app.bsky.embed.images",
                "images": uploaded_images
            }
            
        except Exception as e:
            logger.error(f"Error creating images embed: {e}", exc_info=True)
            return None
    
    async def _upload_image(self, image_url: str) -> Optional[Dict]:
        """
        Download an image from URL and upload it to BlueSky.
        Returns the blob reference.
        """
        try:
            # Download the image
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, headers=headers, timeout=15) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to download image: {image_url} (HTTP {response.status})")
                        return None
                    
                    image_data = await response.read()
                    content_type = response.headers.get('Content-Type', 'image/jpeg')
                    
                    # BlueSky has a 1MB limit per image
                    if len(image_data) > 1000000:
                        logger.warning(f"Image too large (>{len(image_data)} bytes): {image_url}")
                        return None
            
            # Upload to BlueSky
            upload_headers = {
                "Authorization": f"Bearer {self.session['accessJwt']}",
                "Content-Type": content_type
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/xrpc/com.atproto.repo.uploadBlob",
                    data=image_data,
                    headers=upload_headers,
                    timeout=30
                ) as response:
                    
                    if response.status == 200:
                        result = await response.json()
                        return result.get("blob")
                    else:
                        error_text = await response.text()
                        logger.error(f"Image upload failed: HTTP {response.status} - {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.warning(f"Timeout downloading/uploading image: {image_url}")
            return None
        except Exception as e:
            logger.error(f"Error uploading image {image_url}: {e}", exc_info=True)
            return None
    
    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication session"""
        if self.session and self.session_expires:
            # Check if session is still valid (with some buffer)
            if datetime.utcnow() < self.session_expires:
                logger.debug("Using existing BlueSky session")
                return True
        
        logger.info("Authenticating with BlueSky...")
        return await self._authenticate()
    
    async def _authenticate(self) -> bool:
        """Authenticate with BlueSky"""
        try:
            auth_data = {
                "identifier": self.handle,
                "password": self.password
            }
            
            logger.debug(f"Authenticating with handle: {self.handle}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/xrpc/com.atproto.server.createSession",
                    json=auth_data,
                    timeout=30
                ) as response:
                    
                    if response.status == 200:
                        self.session = await response.json()
                        # Session typically expires in 2 hours, refresh after 1.5 hours
                        # Use timedelta to properly add time
                        self.session_expires = datetime.utcnow() + timedelta(hours=1, minutes=30)
                        logger.info(f"BlueSky authentication successful. Session expires at {self.session_expires}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"BlueSky authentication failed: HTTP {response.status} - {error_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"BlueSky authentication error: {e}", exc_info=True)
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
    
    def _format_post_text(self, post: DevlogPost, max_length: int = 300) -> str:
        """Format post content for BlueSky using full_content first paragraph"""
        # Start with title
        title = post.title.strip()
        
        # Get first paragraph from full_content
        content_source = post.full_content if hasattr(post, 'full_content') and post.full_content else post.content
        first_paragraph = self._extract_first_paragraph(content_source)
        
        # Calculate remaining space for content
        # Format: [title]\n\n[content]\n\n[link]
        link_text = f"\n\nLearn More => {post.link}"
        remaining_space = max_length - len(title) - len(link_text) - 4  # 4 for "\n\n" after title
        
        # Build post text
        post_text = title
        
        if first_paragraph and remaining_space > 20:
            # Truncate first paragraph to fit
            content_preview = self._truncate_content(first_paragraph, remaining_space)
            post_text += f"\n\n{content_preview}"
        
        # Add link
        post_text += link_text
        
        return post_text
    
    def _truncate_content(self, content: str, max_length: int) -> str:
        """Truncate content to specified length"""
        if len(content) <= max_length:
            return content
        
        # Try to truncate at a sentence boundary
        sentences = content.split('. ')
        truncated = ""
        
        for sentence in sentences:
            if len(truncated + sentence + '. ') <= max_length - 3:
                truncated += sentence + '. '
            else:
                break
        
        if truncated:
            return truncated.rstrip() + "..."
        
        # If no sentence boundary found, truncate at word boundary
        words = content.split()
        truncated = ""
        
        for word in words:
            if len(truncated + word + ' ') <= max_length - 3:
                truncated += word + ' '
            else:
                break
        
        return truncated.rstrip() + "..." if truncated else content[:max_length-3] + "..."
    
    async def _create_link_embed(self, url: str, title: str) -> Dict:
        """Create a link embed for BlueSky post (fallback when no images)"""
        try:
            # Get link metadata
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Extract basic metadata
                        description = self._extract_meta_description(html)
                        
                        return {
                            "$type": "app.bsky.embed.external",
                            "external": {
                                "uri": url,
                                "title": title,
                                "description": description or "Check out this devlog update!"
                            }
                        }
        except Exception as e:
            logger.debug(f"Could not create link embed: {e}")
        
        # Return basic embed without metadata if fetch fails
        return {
            "$type": "app.bsky.embed.external",
            "external": {
                "uri": url,
                "title": title,
                "description": "New devlog update!"
            }
        }
    
    def _extract_meta_description(self, html: str) -> Optional[str]:
        """Extract meta description from HTML"""
        import re
        
        # Look for meta description
        pattern = r'<meta\s+(?:name=["\']description["\']|property=["\']og:description["\'])\s+content=["\']([^"\']+)["\']'
        match = re.search(pattern, html, re.IGNORECASE)
        
        if match:
            return match.group(1)[:200]  # Limit description length
        
        return None
    
    async def test_connection(self) -> bool:
        """Test BlueSky connection"""
        try:
            if await self._authenticate():
                logger.info(f"BlueSky connection test successful for handle: {self.handle}")
                return True
            else:
                logger.error("BlueSky connection test failed")
                return False
        except Exception as e:
            logger.error(f"BlueSky connection test failed: {e}", exc_info=True)
            return False
    
    async def _refresh_session(self) -> bool:
        """Refresh authentication session"""
        if not self.session:
            return await self._authenticate()
        
        try:
            headers = {
                "Authorization": f"Bearer {self.session['refreshJwt']}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/xrpc/com.atproto.server.refreshSession",
                    headers=headers,
                    timeout=30
                ) as response:
                    
                    if response.status == 200:
                        self.session = await response.json()
                        # Use timedelta to properly add time
                        self.session_expires = datetime.utcnow() + timedelta(hours=1, minutes=30)
                        logger.info("BlueSky session refreshed")
                        return True
                    else:
                        logger.error(f"BlueSky session refresh failed: HTTP {response.status}")
                        return await self._authenticate()
                        
        except Exception as e:
            logger.error(f"BlueSky session refresh error: {e}", exc_info=True)
            return await self._authenticate()