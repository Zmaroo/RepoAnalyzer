// Class definition
class User {
    // Properties
    name = null;
    age = null;
    
    // Constructor
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }
    
    // Method with validation
    function isValid() {
        return typeof this.name == "string" && 
               typeof this.age == "integer" && 
               this.age >= 0;
    }
    
    // Method with return value
    function isAdult() {
        return this.age >= 18;
    }
    
    // Method with string formatting
    function toString() {
        return format("%s (%d years old)", this.name, this.age);
    }
    
    // Static method
    static function fromTable(table) {
        if ("name" in table && "age" in table) {
            return User(table.name, table.age);
        }
        throw "Invalid user data";
    }
}

// Function with default parameter
function createGreeting(name, prefix = "Hello") {
    return format("%s, %s!", prefix, name);
}

// Function with variable arguments
function processUsers(...) {
    local results = [];
    for (local i = 0; i < vargv.len(); i++) {
        local user = vargv[i];
        if (user instanceof User) {
            results.append(user.toString());
        }
    }
    return results;
}

// Higher-order function
function processWithCallback(users, callback) {
    local results = [];
    foreach (user in users) {
        results.append(callback(user));
    }
    return results;
}

// Generator function
function userGenerator(users) {
    local index = 0;
    return function() {
        if (index < users.len()) {
            return users[index++];
        }
        return null;
    }
}

// Function returning function (closure)
function createAgeChecker(minAge) {
    return function(user) {
        return user.age >= minAge;
    }
}

// Function with error handling
function validateUser(user) {
    try {
        if (!user.isValid()) {
            throw "Invalid user";
        }
        return true;
    } catch (e) {
        print("Validation error: " + e);
        return false;
    }
}

// Function using table as named parameters
function updateUser(params) {
    if (!("user" in params)) {
        throw "User parameter is required";
    }
    
    local user = params.user;
    if ("name" in params) {
        user.name = params.name;
    }
    if ("age" in params) {
        user.age = params.age;
    }
    return user;
}

// Main execution
function main() {
    // Create users
    local user1 = User("John", 25);
    local user2 = User("Alice", 17);
    local users = [user1, user2];
    
    // Test basic functions
    print("Users:");
    foreach (user in users) {
        print(user.toString());
    }
    
    // Test processing with callback
    print("\nProcessing results:");
    local results = processWithCallback(users, function(user) {
        return user.isAdult() ? "Adult: " + user.name : "Minor: " + user.name;
    });
    foreach (result in results) {
        print(result);
    }
    
    // Test generator
    print("\nUsing generator:");
    local nextUser = userGenerator(users);
    local user;
    while ((user = nextUser()) != null) {
        print("Generated: " + user.toString());
    }
    
    // Test age checker
    print("\nChecking ages:");
    local isAdult = createAgeChecker(18);
    foreach (user in users) {
        print(format("%s is adult: %s", user.name, isAdult(user)));
    }
    
    // Test validation
    print("\nValidation:");
    foreach (user in users) {
        print(format("User %s is valid: %s", user.name, validateUser(user)));
    }
    
    // Test update with named parameters
    print("\nUpdating user:");
    local updatedUser = updateUser({
        user = user1,
        name = "John Doe",
        age = 26
    });
    print("Updated: " + updatedUser.toString());
    
    // Test variable arguments
    print("\nProcessing multiple users:");
    local processedUsers = processUsers(user1, user2);
    foreach (result in processedUsers) {
        print(result);
    }
}

// Run main function
main(); 