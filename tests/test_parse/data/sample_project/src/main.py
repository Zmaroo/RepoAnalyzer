"""Main module for the sample project.

This module demonstrates various Python code patterns and features
that can be analyzed by GithubAnalyzer.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class User:
    """User model with basic attributes."""
    id: int
    name: str
    email: str
    created_at: datetime
    
    def to_dict(self) -> Dict[str, any]:
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }

class UserService:
    """Service for managing users."""
    
    def __init__(self, database: 'Database'):
        """Initialize service with database connection."""
        self.db = database
        self.cache: Dict[int, User] = {}
        
    async def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        # Check cache first
        if user_id in self.cache:
            logger.debug(f"Cache hit for user {user_id}")
            return self.cache[user_id]
            
        # Query database
        user_data = await self.db.query_one("SELECT * FROM users WHERE id = ?", user_id)
        if not user_data:
            return None
            
        # Create user object
        user = User(
            id=user_data['id'],
            name=user_data['name'],
            email=user_data['email'],
            created_at=user_data['created_at']
        )
        
        # Update cache
        self.cache[user_id] = user
        return user
        
    async def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        # Validate input
        if not name or not email:
            raise ValueError("Name and email are required")
            
        # Insert into database
        user_id = await self.db.execute(
            "INSERT INTO users (name, email, created_at) VALUES (?, ?, ?)",
            name, email, datetime.now()
        )
        
        # Create and cache user
        user = User(
            id=user_id,
            name=name,
            email=email,
            created_at=datetime.now()
        )
        self.cache[user_id] = user
        
        return user
        
    def clear_cache(self) -> None:
        """Clear the user cache."""
        self.cache.clear()
        
class UserAnalytics:
    """Analytics for user behavior."""
    
    def __init__(self, user_service: UserService):
        """Initialize with user service."""
        self.user_service = user_service
        
    async def get_active_users(self, days: int = 7) -> List[User]:
        """Get list of active users in the last N days."""
        active_users = []
        async for user in self.user_service.db.query(
            "SELECT * FROM users WHERE last_login >= datetime('now', '-? days')",
            days
        ):
            active_users.append(User(
                id=user['id'],
                name=user['name'],
                email=user['email'],
                created_at=user['created_at']
            ))
        return active_users
        
    async def analyze_user_patterns(self) -> Dict[str, any]:
        """Analyze user behavior patterns."""
        return {
            'total_users': await self.user_service.db.count("users"),
            'active_users': len(await self.get_active_users()),
            'inactive_users': len(await self.get_active_users(30))
        }

async def main():
    """Main entry point."""
    # Initialize services
    db = Database("sqlite:///users.db")
    user_service = UserService(db)
    analytics = UserAnalytics(user_service)
    
    # Create some users
    await user_service.create_user("Alice", "alice@example.com")
    await user_service.create_user("Bob", "bob@example.com")
    
    # Analyze patterns
    patterns = await analytics.analyze_user_patterns()
    logger.info(f"User patterns: {patterns}")
    
if __name__ == "__main__":
    asyncio.run(main()) 