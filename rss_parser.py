import feedparser
import re
import logging
import requests
from typing import List, Tuple, Optional
from urllib.parse import urljoin
from dataclasses import dataclass
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

@dataclass
class DevlogPost:
    title: str
    content: str  # Short content from RSS (for Twitter/BlueSky)
    full_content: str  # Full scraped content (for Discord)
    link: str
    pub_date: str
    guid: str
    images: List[str]

class RSSParser:
    def __init__(self, rss_url: str):
        self.rss_url = rss_url
    
    def parse_feed(self) -> List[DevlogPost]:
        """
        Parse the RSS feed and return list of DevlogPost objects.
        
        This implements a hybrid approach:
        1. Poll RSS to detect new posts and get short description/content
        2. Scrape HTML page for full content that matches the RSS description
        3. Extract images from the matched content area only
        """
        try:
            logger.info(f"Parsing RSS feed: {self.rss_url}")
            feed = feedparser.parse(self.rss_url)
            
            if feed.bozo:
                logger.warning(f"RSS feed may have issues: {feed.bozo_exception}")
            
            if not feed.entries:
                logger.warning("No entries found in RSS feed")
                return []
            
            posts = []
            
            for entry in feed.entries:
                try:
                    # Step 1: Get basic info from RSS feed
                    title = entry.title
                    link = entry.link
                    pub_date = getattr(entry, 'published', '')
                    guid = getattr(entry, 'id', entry.link)
                    
                    # Get short content/description from RSS (for Twitter/BlueSky)
                    content_html = ""
                    if hasattr(entry, 'content') and entry.content:
                        content_html = entry.content[0].value
                    elif hasattr(entry, 'summary'):
                        content_html = entry.summary
                    elif hasattr(entry, 'description'):
                        content_html = entry.description
                    
                    # Clean the RSS content to plain text
                    short_content = self.clean_html(content_html)
                    
                    logger.info(f"Processing post: {title}")
                    logger.debug(f"RSS short content preview: {short_content[:100]}...")
                    
                    # Step 2: Scrape HTML page and find content matching RSS description
                    full_content, images = self._scrape_and_match_content(link, short_content)
                    
                    # If scraping failed, use RSS content as fallback
                    if not full_content or full_content.startswith("Error"):
                        logger.warning(f"Using RSS content as fallback for {title}")
                        full_content = short_content
                        # Try to extract images from RSS HTML as fallback
                        if content_html:
                            images = self.extract_images_from_html_string(content_html, link)
                    
                    post = DevlogPost(
                        title=title,
                        content=short_content,  # Short content for Twitter/BlueSky
                        full_content=full_content,  # Full matched content for Discord
                        link=link,
                        pub_date=pub_date,
                        guid=guid,
                        images=images
                    )
                    posts.append(post)
                    logger.info(f"Successfully parsed post: {title} (short: {len(short_content)} chars, full: {len(full_content)} chars, {len(images)} images)")
                    
                except Exception as e:
                    logger.error(f"Error parsing entry '{entry.get('title', 'Unknown')}': {e}")
                    continue
            
            logger.info(f"Successfully parsed {len(posts)} posts from RSS feed")
            return posts
            
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")
            return []
    
    def _scrape_and_match_content(self, url: str, short_content: str) -> Tuple[str, List[str]]:
        """
        Scrape page and find content section that matches the RSS short description.
        This ensures we only get the actual devlog content, not navigation/sidebar elements.
        
        Returns: (matched_full_content, list_of_image_urls)
        """
        try:
            logger.info(f"Scraping and matching content from: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Strategy 1: Look for post_images section (itch.io specific - gallery images)
            post_images_section = soup.find('section', class_='post_images')
            gallery_images = []
            if post_images_section:
                logger.debug("Found post_images section - extracting gallery images")
                gallery_images = self._extract_gallery_images(post_images_section, url)
                logger.info(f"Extracted {len(gallery_images)} gallery images")
            
            # Strategy 2: Look for formatted_body or post_body div (itch.io specific)
            content_body = soup.find('section', class_='post_body') or soup.find('div', class_='formatted_body')
            
            if content_body:
                logger.debug("Found post content body - extracting content")
                full_content = self._extract_text_from_element(content_body)
                
                # Verify this content matches our RSS short description
                if self._content_matches(short_content, full_content):
                    logger.info("Content match confirmed in post body")
                    # Extract inline images from content
                    inline_images = self._extract_images_from_html(content_body, url)
                    # Combine gallery images (first) with inline images
                    all_images = gallery_images + inline_images
                    # Remove duplicates
                    all_images = self._deduplicate_list(all_images)
                    logger.info(f"Total images found: {len(all_images)} (gallery: {len(gallery_images)}, inline: {len(inline_images)})")
                    return full_content, all_images
                else:
                    logger.debug("post_body content doesn't match RSS description")
            
            # Strategy 2: Search for content that matches RSS description
            logger.debug("Searching for matching content sections...")
            matched_content, matched_element = self._find_matching_content_section(soup, short_content)
            
            if matched_content and matched_element:
                logger.info(f"Found matching content section: {len(matched_content)} chars")
                inline_images = self._extract_images_from_html(matched_element, url)
                # Combine gallery images with inline images
                all_images = gallery_images + inline_images
                all_images = self._deduplicate_list(all_images)
                logger.info(f"Total images: {len(all_images)}")
                return matched_content, all_images
            
            # Strategy 3: Fallback to common content containers
            logger.warning("No direct match found, trying common containers...")
            content_containers = [
                ('section', 'post_body'),
                ('div', 'formatted_body'),
                ('div', 'post_body'),
                ('div', 'post-body'),
                ('div', 'content'),
                ('div', 'post-content'),
                ('div', 'entry-content'),
                ('article', None),
                ('main', None)
            ]
            
            for tag, class_name in content_containers:
                if class_name:
                    container = soup.find(tag, class_=class_name)
                else:
                    container = soup.find(tag)
                
                if container:
                    content = self._extract_text_from_element(container)
                    # Check if this content is similar enough to RSS description
                    if len(content) > 50 and self._content_similarity(short_content, content) > 0.3:
                        logger.info(f"Using {tag}.{class_name} container as fallback")
                        inline_images = self._extract_images_from_html(container, url)
                        all_images = gallery_images + inline_images
                        all_images = self._deduplicate_list(all_images)
                        return content, all_images
            
            logger.error("Could not find matching content on page")
            # Return gallery images even if content matching failed
            return "Error: Could not locate devlog content on page", gallery_images
            
        except requests.Timeout:
            logger.error(f"Timeout while scraping {url}")
            return "Error: Content unavailable (timeout)", []
        except requests.RequestException as e:
            logger.error(f"Network error scraping {url}: {e}")
            return "Error: Content unavailable (network error)", []
        except Exception as e:
            logger.error(f"Error parsing HTML from {url}: {e}")
            return "Error: Content unavailable (parsing error)", []
    
    def _find_matching_content_section(self, soup, reference_text: str) -> Tuple[Optional[str], Optional[any]]:
        """
        Search through page elements to find the section that best matches the reference text.
        Returns (matched_text, matched_element) or (None, None) if no good match found.
        """
        # Normalize reference text for comparison
        ref_normalized = self._normalize_text(reference_text)
        ref_words = set(ref_normalized.split())
        
        # Get the first few sentences from reference as a strong indicator
        ref_start = ' '.join(reference_text.split()[:30])  # First 30 words
        
        best_match_score = 0
        best_match_text = None
        best_match_element = None
        
        # Search through potential content containers
        potential_containers = soup.find_all(['div', 'article', 'section'], recursive=True)
        
        for container in potential_containers:
            # Skip very small containers
            text = container.get_text(strip=True)
            if len(text) < 100:
                continue
            
            # Skip containers with lots of links (likely navigation)
            links = container.find_all('a')
            if len(links) > 10:
                continue
            
            # Check if this container has the start of our reference text
            if ref_start[:50] in text:
                logger.debug(f"Found container with matching start text")
                full_text = self._extract_text_from_element(container)
                return full_text, container
            
            # Calculate similarity score
            text_normalized = self._normalize_text(text)
            text_words = set(text_normalized.split())
            
            # Calculate word overlap
            if ref_words:
                overlap = len(ref_words.intersection(text_words))
                overlap_ratio = overlap / len(ref_words)
                
                # Prefer containers with higher overlap
                if overlap_ratio > best_match_score and overlap_ratio > 0.5:
                    best_match_score = overlap_ratio
                    best_match_text = self._extract_text_from_element(container)
                    best_match_element = container
        
        if best_match_score > 0.5:
            logger.info(f"Found best matching section with score: {best_match_score:.2f}")
            return best_match_text, best_match_element
        
        return None, None
    
    def _content_matches(self, short_text: str, full_text: str, threshold: float = 0.7) -> bool:
        """
        Check if full_text contains/matches the short_text content.
        Returns True if they're similar enough.
        """
        # Normalize both texts
        short_normalized = self._normalize_text(short_text)
        full_normalized = self._normalize_text(full_text)
        
        # Check if short content is substring of full content
        if short_normalized in full_normalized:
            logger.debug("Short content is substring of full content")
            return True
        
        # Check similarity ratio
        similarity = self._content_similarity(short_text, full_text)
        logger.debug(f"Content similarity: {similarity:.2f}")
        
        return similarity >= threshold
    
    def _content_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0.0 to 1.0)"""
        # Normalize texts
        t1 = self._normalize_text(text1)
        t2 = self._normalize_text(text2)
        
        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, t1, t2).ratio()
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison - remove extra whitespace, lowercase"""
        text = re.sub(r'\s+', ' ', text)  # Multiple whitespace to single space
        text = text.lower().strip()
        return text
    
    def _extract_text_from_element(self, element) -> str:
        """
        Extract text from HTML element, preserving structure.
        Handles paragraphs, headings, lists, bold, italic, etc.
        Skips content inside post_header (title area).
        """
        if not element:
            return ""
        
        text_parts = []
        
        # Process paragraph and heading elements
        for tag in element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
            # Skip unwanted containers
            if tag.find_parent(['script', 'style', 'noscript']):
                continue
            if tag.find_parent(class_='post_header'):  # <-- skip post_header
                continue
            
            # --- Inline formatting replacements ---
            for bold_tag in tag.find_all(['strong', 'b']):
                bold_tag.string = f"**{bold_tag.get_text(strip=True)}**"
            
            for italic_tag in tag.find_all(['em', 'i']):
                italic_tag.string = f"*{italic_tag.get_text(strip=True)}*"
            
            # Now extract cleaned text
            text = tag.get_text(strip=True)
            if not text or len(text) < 3:
                continue
            
            # Format based on tag type
            if tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text_parts.append(f"### {text}\n")
            elif tag.name == 'li':
                text_parts.append(f"• {text}")
            elif tag.name == 'p':
                text_parts.append(text)
        
        # If no structured content found, get text with basic separation
        if not text_parts:
            for script in element(['script', 'style', 'noscript']):
                script.decompose()
            
            text = element.get_text(separator='\n', strip=True)
            return self.clean_html(text)
        
        # Join and clean up
        full_text = '\n\n'.join(text_parts)
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)  # Max 2 consecutive newlines
        full_text = full_text.strip()
        
        return full_text

    def _extract_gallery_images(self, section, base_url: str) -> List[str]:
        """
        Extract images from itch.io's post_images gallery section.
        Prefers high-quality 'original' links over thumbnails.
        """
        images = []
        
        # Find all <a> tags with data-image_lightbox (these contain full-size links)
        lightbox_links = section.find_all('a', attrs={'data-image_lightbox': ''})
        
        for link in lightbox_links:
            # Prefer href (original/full quality) over img src (thumbnail)
            full_url = link.get('href', '')
            if full_url:
                # Normalize URL
                full_url = self._normalize_image_url(full_url, base_url)
                
                # Check if it's a valid image
                if self._is_valid_gallery_image(full_url):
                    images.append(full_url)
                    logger.debug(f"Found gallery image (original): {full_url}")
                    continue
            
            # Fallback to img src if href not available
            img_tag = link.find('img')
            if img_tag:
                src = img_tag.get('src', img_tag.get('data-src', ''))
                if src:
                    src = self._normalize_image_url(src, base_url)
                    if self._is_valid_image(src, img_tag):
                        images.append(src)
                        logger.debug(f"Found gallery image (thumbnail): {src}")
        
        # If no lightbox links, try regular img tags in the section
        if not images:
            img_tags = section.find_all('img')
            for img in img_tags:
                src = img.get('src', img.get('data-src', ''))
                if src:
                    src = self._normalize_image_url(src, base_url)
                    if self._is_valid_image(src, img):
                        images.append(src)
                        logger.debug(f"Found gallery image: {src}")
        
        return images
    
    def _is_valid_gallery_image(self, url: str) -> bool:
        """Check if a URL is a valid gallery image (less strict than regular images)"""
        url_lower = url.lower()
        
        # Must have valid image extension or be from itch.zone
        valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')
        
        if 'img.itch.zone' in url_lower:
            return True
        
        if any(ext in url_lower for ext in valid_extensions):
            return True
        
        return False
    
    def _extract_images_from_html(self, element, base_url: str) -> List[str]:
        """Extract all valid images from an HTML element"""
        images = []
        
        img_tags = element.find_all('img')
        
        for img in img_tags:
            src = img.get('src', img.get('data-src', ''))
            if not src:
                continue
            
            # Convert relative URLs to absolute
            src = self._normalize_image_url(src, base_url)
            
            # Filter out icons, avatars, and tiny images
            if self._is_valid_image(src, img):
                images.append(src)
                logger.debug(f"Found image: {src}")
        
        # Remove duplicates while preserving order
        return self._deduplicate_list(images)
    
    def extract_images_from_html_string(self, html_string: str, base_url: str) -> List[str]:
        """Extract images from HTML string (fallback for RSS content)"""
        try:
            soup = BeautifulSoup(html_string, 'html.parser')
            return self._extract_images_from_html(soup, base_url)
        except Exception as e:
            logger.error(f"Error extracting images from HTML string: {e}")
            return []
    
    def _normalize_image_url(self, src: str, base_url: str) -> str:
        """Convert relative image URLs to absolute"""
        if src.startswith('//'):
            return 'https:' + src
        elif src.startswith('/'):
            return urljoin(base_url, src)
        elif not src.startswith(('http://', 'https://')):
            return urljoin(base_url, src)
        return src
    
    def _is_valid_image(self, src: str, img_tag) -> bool:
        """Check if an image should be included"""
        src_lower = src.lower()
        
        # Exclude common icon/avatar patterns
        exclude_patterns = [
            'icon', 'avatar', 'logo', 'badge', 'button',
            'emoji', 'smil', 'pixel.gif', '1x1', 'spacer'
        ]
        
        for pattern in exclude_patterns:
            if pattern in src_lower:
                return False
        
        # Check image dimensions if available
        width = img_tag.get('width', '')
        height = img_tag.get('height', '')
        
        try:
            if width and int(width) < 50:
                return False
            if height and int(height) < 50:
                return False
        except (ValueError, TypeError):
            pass
        
        # Must have valid image extension
        valid_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')
        if not any(src_lower.endswith(ext) or ext in src_lower for ext in valid_extensions):
            return False
        
        return True
    
    def _deduplicate_list(self, items: List[str]) -> List[str]:
        """Remove duplicates while preserving order"""
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result
    
    def clean_html(self, html_content: str) -> str:
        """Clean HTML content for social media posting"""
        if not html_content:
            return ""
        
        try:
            # Replace common HTML entities
            entities = {
                '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
                '&quot;': '"', '&#39;': "'", '&mdash;': '—', '&ndash;': '–',
                '&hellip;': '...', '&rsquo;': "'", '&lsquo;': "'",
                '&rdquo;': '"', '&ldquo;': '"'
            }
            
            for entity, replacement in entities.items():
                html_content = html_content.replace(entity, replacement)
            
            # Convert <br> tags to newlines
            html_content = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
            
            # Convert <p> tags to double newlines
            html_content = re.sub(r'</p>\s*<p[^>]*>', '\n\n', html_content, flags=re.IGNORECASE)
            html_content = re.sub(r'</?p[^>]*>', '\n', html_content, flags=re.IGNORECASE)
            
            # Remove all other HTML tags
            html_content = re.sub(r'<[^>]+>', '', html_content)
            
            # Clean up whitespace
            html_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', html_content)  # Max 2 newlines
            html_content = re.sub(r'[ \t]+', ' ', html_content)  # Multiple spaces to single
            html_content = html_content.strip()
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error cleaning HTML content: {e}")
            return html_content
    
    def truncate_content(self, content: str, max_length: int) -> str:
        """Truncate content to max_length with ellipsis"""
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