/**
 * User service client implementation.
 * This module provides a JavaScript interface to the Python user service.
 */

class UserServiceClient {
    /**
     * Initialize the user service client.
     * @param {string} baseUrl - Base URL for the API
     */
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
        this.cache = new Map();
    }
    
    /**
     * Get a user by ID.
     * @param {number} userId - User ID to fetch
     * @returns {Promise<User>} User object
     */
    async getUser(userId) {
        // Check cache first
        if (this.cache.has(userId)) {
            console.debug(`Cache hit for user ${userId}`);
            return this.cache.get(userId);
        }
        
        // Fetch from API
        const response = await fetch(`${this.baseUrl}/users/${userId}`);
        if (!response.ok) {
            throw new Error(`Failed to fetch user: ${response.statusText}`);
        }
        
        const userData = await response.json();
        const user = new User(
            userData.id,
            userData.name,
            userData.email,
            new Date(userData.created_at)
        );
        
        // Update cache
        this.cache.set(userId, user);
        return user;
    }
    
    /**
     * Create a new user.
     * @param {string} name - User's name
     * @param {string} email - User's email
     * @returns {Promise<User>} Created user
     */
    async createUser(name, email) {
        // Validate input
        if (!name || !email) {
            throw new Error("Name and email are required");
        }
        
        // Send to API
        const response = await fetch(`${this.baseUrl}/users`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, email })
        });
        
        if (!response.ok) {
            throw new Error(`Failed to create user: ${response.statusText}`);
        }
        
        const userData = await response.json();
        const user = new User(
            userData.id,
            userData.name,
            userData.email,
            new Date(userData.created_at)
        );
        
        // Update cache
        this.cache.set(user.id, user);
        return user;
    }
    
    /**
     * Clear the user cache.
     */
    clearCache() {
        this.cache.clear();
    }
}

class UserAnalyticsClient {
    /**
     * Initialize the analytics client.
     * @param {UserServiceClient} userService - User service client
     */
    constructor(userService) {
        this.userService = userService;
    }
    
    /**
     * Get active users from the last N days.
     * @param {number} days - Number of days to look back
     * @returns {Promise<User[]>} List of active users
     */
    async getActiveUsers(days = 7) {
        const response = await fetch(
            `${this.userService.baseUrl}/analytics/active-users?days=${days}`
        );
        
        if (!response.ok) {
            throw new Error(`Failed to fetch active users: ${response.statusText}`);
        }
        
        const usersData = await response.json();
        return usersData.map(userData => new User(
            userData.id,
            userData.name,
            userData.email,
            new Date(userData.created_at)
        ));
    }
    
    /**
     * Analyze user patterns.
     * @returns {Promise<Object>} Analysis results
     */
    async analyzeUserPatterns() {
        const response = await fetch(`${this.userService.baseUrl}/analytics/patterns`);
        if (!response.ok) {
            throw new Error(`Failed to analyze patterns: ${response.statusText}`);
        }
        
        return response.json();
    }
}

// Example usage
async function main() {
    const userService = new UserServiceClient('http://localhost:8000/api');
    const analytics = new UserAnalyticsClient(userService);
    
    try {
        // Create some users
        const alice = await userService.createUser('Alice', 'alice@example.com');
        const bob = await userService.createUser('Bob', 'bob@example.com');
        
        // Get user info
        const user = await userService.getUser(alice.id);
        console.log('User:', user);
        
        // Analyze patterns
        const patterns = await analytics.analyzeUserPatterns();
        console.log('User patterns:', patterns);
        
    } catch (error) {
        console.error('Error:', error.message);
    }
}

// Run if not imported as a module
if (typeof require !== 'undefined' && require.main === module) {
    main().catch(console.error);
} 