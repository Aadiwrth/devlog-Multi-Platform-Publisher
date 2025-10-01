import discord
import asyncio
import logging
from typing import List

logger = logging.getLogger(__name__)

class DiscordPoster:
    def __init__(self, bot_token: str, channel_id: int):
        self.bot_token = bot_token
        self.channel_id = channel_id
    
    async def post(self, post) -> bool:
        """Post content to Discord channel using full_content"""
        try:
            intents = discord.Intents.default()
            intents.message_content = True
            client = discord.Client(intents=intents)
            
            success = False
            
            @client.event
            async def on_ready():
                nonlocal success
                try:
                    channel = client.get_channel(self.channel_id)
                    if not channel:
                        logger.error(f"Discord channel {self.channel_id} not found")
                        return
                    
                    # Use full_content (scraped from HTML) for Discord
                    content_to_use = post.full_content if hasattr(post, 'full_content') else post.content
                    
                    # Create main embed with full scraped content
                    embed = discord.Embed(
                        title=post.title,
                        description=self._truncate_description(content_to_use),
                        url=post.link,
                        color=0x00ff88,
                        timestamp=discord.utils.utcnow()
                    )
                    
                    # Add footer
                    embed.set_footer(
                        text=f"New Devlog • {post.pub_date}" if post.pub_date else "New Devlog",
                        icon_url="https://i.postimg.cc/nLdWVm6Y/logo.jpg"
                    )
                    
                    # Add first image as thumbnail if available
                    if post.images:
                        embed.set_image(url=post.images[0])
                    
                    # Send main embed
                    await channel.send(embed=embed)
                    logger.info(f"Sent main embed for: {post.title} (using full_content: {len(content_to_use)} chars)")
                    
                    # Send additional images if there are more
                    if len(post.images) > 1:
                        # Discord allows up to 10 embeds per message, but we'll limit to 4 total
                        for img_url in post.images[1:4]:
                            try:
                                img_embed = discord.Embed(color=0x00ff88)
                                img_embed.set_image(url=img_url)
                                await channel.send(embed=img_embed)
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                logger.error(f"Error sending image {img_url}: {e}")
                    
                    # If content is very long, send continuation messages
                    if len(content_to_use) > 4000:
                        remaining_content = content_to_use[4000:]
                        chunks = self._split_content(remaining_content)
                        
                        for chunk in chunks[:2]:  # Limit to 2 additional messages
                            try:
                                continuation_embed = discord.Embed(
                                    description=chunk,
                                    color=0x00ff88
                                )
                                await channel.send(embed=continuation_embed)
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                logger.error(f"Error sending continuation: {e}")
                    
                    logger.info(f"Successfully posted to Discord: {post.title}")
                    success = True
                    
                except Exception as e:
                    logger.error(f"Error in Discord on_ready: {e}")
                finally:
                    await client.close()
            
            @client.event
            async def on_error(event, *args, **kwargs):
                logger.error(f"Discord client error in {event}: {args}")
            
            # Start the client with timeout
            try:
                await asyncio.wait_for(client.start(self.bot_token), timeout=30)
            except asyncio.TimeoutError:
                logger.error("Discord client connection timeout")
                await client.close()
            
            return success
            
        except Exception as e:
            logger.error(f"Error posting to Discord: {e}")
            return False
    
    def _truncate_description(self, content: str, max_length: int = 4000) -> str:
        """
        Truncate content to fit Discord embed description limit (4096 chars)
        Using 4000 to leave room for formatting
        """
        if len(content) <= max_length:
            return content
        
        # Try to truncate at a paragraph boundary
        paragraphs = content.split('\n\n')
        truncated = ""
        
        for para in paragraphs:
            if len(truncated + para + '\n\n') <= max_length - 3:
                truncated += para + '\n\n'
            else:
                break
        
        if truncated:
            return truncated.rstrip() + "..."
        
        # If no paragraph boundary found, truncate at sentence boundary
        sentences = content.split('. ')
        truncated = ""
        
        for sentence in sentences:
            if len(truncated + sentence + '. ') <= max_length - 3:
                truncated += sentence + '. '
            else:
                break
        
        if truncated:
            return truncated.rstrip() + "..."
        
        # Last resort: truncate at word boundary
        words = content.split()
        truncated = ""
        
        for word in words:
            if len(truncated + word + ' ') <= max_length - 3:
                truncated += word + ' '
            else:
                break
        
        return truncated.rstrip() + "..." if truncated else content[:max_length-3] + "..."
    
    def _split_content(self, content: str, chunk_size: int = 4000) -> List[str]:
        """Split long content into chunks for multiple messages"""
        chunks = []
        current_chunk = ""
        
        paragraphs = content.split('\n\n')
        
        for para in paragraphs:
            if len(current_chunk + para + '\n\n') <= chunk_size:
                current_chunk += para + '\n\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.rstrip())
                current_chunk = para + '\n\n'
        
        if current_chunk:
            chunks.append(current_chunk.rstrip())
        
        return chunks
    
    async def test_connection(self) -> bool:
        """Test Discord connection and permissions"""
        try:
            intents = discord.Intents.default()
            client = discord.Client(intents=intents)
            
            success = False
            
            @client.event
            async def on_ready():
                nonlocal success
                try:
                    channel = client.get_channel(self.channel_id)
                    if channel:
                        permissions = channel.permissions_for(channel.guild.me)
                        if permissions.send_messages and permissions.embed_links:
                            logger.info(f"Discord connection test successful for channel: {channel.name}")
                            success = True
                        else:
                            logger.error("Discord bot lacks required permissions (send_messages, embed_links)")
                    else:
                        logger.error(f"Discord channel {self.channel_id} not found or not accessible")
                except Exception as e:
                    logger.error(f"Error in Discord connection test: {e}")
                finally:
                    await client.close()
            
            await asyncio.wait_for(client.start(self.bot_token), timeout=15)
            return success
            
        except Exception as e:
            logger.error(f"Discord connection test failed: {e}")
            return False