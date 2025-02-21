const std = @import("std");
const Allocator = std.mem.Allocator;
const ArrayList = std.ArrayList;
const StringHashMap = std.StringHashMap;

// Error set definition
const UserError = error{
    InvalidAge,
    InvalidName,
    UserNotFound,
};

// User struct definition
const User = struct {
    name: []const u8,
    age: u32,

    // Constructor
    pub fn init(allocator: *Allocator, name: []const u8, age: u32) !User {
        if (age > 150) {
            return UserError.InvalidAge;
        }
        const name_copy = try allocator.dupe(u8, name);
        return User{
            .name = name_copy,
            .age = age,
        };
    }

    // Method to check if user is adult
    pub fn isAdult(self: User) bool {
        return self.age >= 18;
    }

    // Method to format user as string
    pub fn format(self: User, writer: anytype) !void {
        try writer.print("{s} ({d} years old)", .{ self.name, self.age });
    }

    // Method to validate user
    pub fn validate(self: User) !void {
        if (self.name.len == 0) {
            return UserError.InvalidName;
        }
        if (self.age > 150) {
            return UserError.InvalidAge;
        }
    }
};

// UserRegistry for managing users
const UserRegistry = struct {
    users: StringHashMap(User),
    allocator: *Allocator,

    // Constructor
    pub fn init(allocator: *Allocator) UserRegistry {
        return UserRegistry{
            .users = StringHashMap(User).init(allocator),
            .allocator = allocator,
        };
    }

    // Method to add user
    pub fn addUser(self: *UserRegistry, user: User) !void {
        try self.users.put(user.name, user);
    }

    // Method to get user
    pub fn getUser(self: UserRegistry, name: []const u8) ?User {
        return self.users.get(name);
    }

    // Method to remove user
    pub fn removeUser(self: *UserRegistry, name: []const u8) bool {
        return self.users.remove(name);
    }

    // Method to get all users
    pub fn getAllUsers(self: UserRegistry) []User {
        var users = ArrayList(User).init(self.allocator);
        var it = self.users.iterator();
        while (it.next()) |entry| {
            users.append(entry.value_ptr.*) catch continue;
        }
        return users.toOwnedSlice();
    }

    // Cleanup
    pub fn deinit(self: *UserRegistry) void {
        self.users.deinit();
    }
};

// Generic function to find user
fn findUser(comptime T: type, users: []const T, name: []const u8) ?T {
    for (users) |user| {
        if (std.mem.eql(u8, user.name, name)) {
            return user;
        }
    }
    return null;
}

// Function with error union return type
fn createUser(allocator: *Allocator, name: []const u8, age: u32) !User {
    if (age > 150) {
        return UserError.InvalidAge;
    }
    return User.init(allocator, name, age);
}

// Function with optional parameter
fn createGreeting(name: []const u8, prefix: ?[]const u8) []const u8 {
    const default_prefix = "Hello";
    const actual_prefix = prefix orelse default_prefix;
    return std.fmt.allocPrint(
        allocator,
        "{s}, {s}!",
        .{ actual_prefix, name },
    ) catch return "Error creating greeting";
}

// Function that returns multiple values in a tuple
fn getUserStats(users: []const User) struct { total: usize, adults: usize } {
    var adult_count: usize = 0;
    for (users) |user| {
        if (user.isAdult()) {
            adult_count += 1;
        }
    }
    return .{
        .total = users.len,
        .adults = adult_count,
    };
}

// Async function example
fn processUserAsync(user: User) !void {
    const stdout = std.io.getStdOut().writer();
    try stdout.print("Processing user: ", .{});
    try user.format(stdout);
    try stdout.print("\n", .{});
}

// Main function
pub fn main() !void {
    // Initialize allocator
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = &gpa.allocator();

    // Create stdout writer
    const stdout = std.io.getStdOut().writer();

    // Create users
    const user1 = try createUser(allocator, "John", 25);
    const user2 = try createUser(allocator, "Alice", 17);
    var users = [_]User{ user1, user2 };

    // Test basic functions
    try stdout.print("Users:\n", .{});
    for (users) |user| {
        try user.format(stdout);
        try stdout.print("\n", .{});
    }

    // Test user registry
    var registry = UserRegistry.init(allocator);
    defer registry.deinit();

    try registry.addUser(user1);
    try registry.addUser(user2);

    // Test user finding
    try stdout.print("\nFinding user:\n", .{});
    if (findUser(User, &users, "John")) |user| {
        try user.format(stdout);
        try stdout.print("\n", .{});
    }

    // Test user stats
    const stats = getUserStats(&users);
    try stdout.print("\nStats:\n", .{});
    try stdout.print("Total users: {d}\n", .{stats.total});
    try stdout.print("Adult users: {d}\n", .{stats.adults});

    // Test greeting
    const greeting = createGreeting("Bob", null);
    try stdout.print("\nGreeting: {s}\n", .{greeting});

    // Test async processing
    try stdout.print("\nAsync processing:\n", .{});
    try processUserAsync(user1);
    try processUserAsync(user2);

    // Test validation
    try stdout.print("\nValidation:\n", .{});
    user1.validate() catch |err| {
        try stdout.print("Validation error: {}\n", .{err});
    };
} 