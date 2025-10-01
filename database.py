import sqlite3
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "devlog_posts.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with posts table"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS posted_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guid TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                discord_posted BOOLEAN DEFAULT FALSE,
                twitter_posted BOOLEAN DEFAULT FALSE,
                bluesky_posted BOOLEAN DEFAULT FALSE
            )
            ''')
            
            # Add index for faster lookups
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_guid ON posted_entries(guid)
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def is_post_processed(self, guid: str) -> Dict[str, bool]:
        """Check if a post has been processed for each platform"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT discord_posted, twitter_posted, bluesky_posted 
            FROM posted_entries WHERE guid = ?
            ''', (guid,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'discord': bool(result[0]),
                    'twitter': bool(result[1]),
                    'bluesky': bool(result[2])
                }
            return {'discord': False, 'twitter': False, 'bluesky': False}
            
        except Exception as e:
            logger.error(f"Error checking post status: {e}")
            return {'discord': False, 'twitter': False, 'bluesky': False}
    
    def mark_post_sent(self, guid: str, title: str, platform: str):
        """Mark a post as sent for a specific platform"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert or ignore the post entry
            cursor.execute('''
            INSERT OR IGNORE INTO posted_entries (guid, title) VALUES (?, ?)
            ''', (guid, title))
            
            # Update the specific platform
            if platform in ['discord', 'twitter', 'bluesky']:
                platform_column = f"{platform}_posted"
                cursor.execute(f'''
                UPDATE posted_entries SET {platform_column} = TRUE WHERE guid = ?
                ''', (guid,))
            else:
                logger.warning(f"Unknown platform: {platform}")
            
            conn.commit()
            conn.close()
            logger.debug(f"Marked {guid} as posted to {platform}")
            
        except Exception as e:
            logger.error(f"Error marking post as sent: {e}")
    
    def get_post_stats(self) -> Dict:
        """Get statistics about posted entries"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT 
                COUNT(*) as total_posts,
                SUM(discord_posted) as discord_posts,
                SUM(twitter_posted) as twitter_posts,
                SUM(bluesky_posted) as bluesky_posts
            FROM posted_entries
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            return {
                'total_posts': result[0],
                'discord_posts': result[1],
                'twitter_posts': result[2],
                'bluesky_posts': result[3]
            }
            
        except Exception as e:
            logger.error(f"Error getting post stats: {e}")
            return {'total_posts': 0, 'discord_posts': 0, 'twitter_posts': 0, 'bluesky_posts': 0}
    
    def add_platform_column(self, platform_name: str):
        """Add a new platform column to the database (for future extensions)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            column_name = f"{platform_name}_posted"
            cursor.execute(f'''
            ALTER TABLE posted_entries ADD COLUMN {column_name} BOOLEAN DEFAULT FALSE
            ''')
            
            conn.commit()
            conn.close()
            logger.info(f"Added column for platform: {platform_name}")
            
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                logger.debug(f"Column for {platform_name} already exists")
            else:
                logger.error(f"Error adding platform column: {e}")
        except Exception as e:
            logger.error(f"Error adding platform column: {e}")