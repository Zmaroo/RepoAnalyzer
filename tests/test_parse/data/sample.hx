package;

// Type definition
typedef ProcessResult = {
    var success:Bool;
    var message:String;
}

// Interface definition
interface Processable {
    public function process():ProcessResult;
}

// Class definition
class User implements Processable {
    public var name(default, null):String;
    public var age(default, null):Int;
    
    // Constructor
    public function new(name:String, age:Int) {
        this.name = name;
        this.age = age;
    }
    
    // Interface implementation
    public function process():ProcessResult {
        return {
            success: age >= 18,
            message: if (age >= 18) "Adult user" else "Minor user"
        };
    }
    
    // Method with type parameters
    public function format(?verbose:Bool = false):String {
        return if (verbose)
            '$name is $age years old'
        else
            '$name ($age)';
    }
    
    // Static method
    public static function fromJson(json:Dynamic):User {
        return new User(json.name, json.age);
    }
}

// Generic class
class UserCollection<T:User> {
    private var users:Array<T>;
    
    public function new() {
        users = [];
    }
    
    public function add(user:T):Void {
        users.push(user);
    }
    
    public function getUsers():Array<T> {
        return users.copy();
    }
}

// Abstract type
abstract Age(Int) {
    public inline function new(age:Int) {
        this = age;
    }
    
    @:from
    static public function fromInt(age:Int):Age {
        if (age < 0) throw "Age cannot be negative";
        return new Age(age);
    }
    
    @:to
    public function toString():String {
        return '$this years old';
    }
    
    public function isAdult():Bool {
        return this >= 18;
    }
}

// Class with generics and type constraints
class UserProcessor<T:User & Processable> {
    public function new() {}
    
    public function processUsers(users:Array<T>):Array<ProcessResult> {
        return users.map(user -> user.process());
    }
}

// Main class
class Main {
    // Function with optional arguments
    static function createGreeting(?prefix:String = "Hello", name:String):String {
        return '$prefix, $name!';
    }
    
    // Function with type parameters
    static function findUser<T:User>(users:Array<T>, name:String):Null<T> {
        return users.find(user -> user.name == name);
    }
    
    // Async function
    static function processUserAsync(user:User):Promise<ProcessResult> {
        return new Promise((resolve, reject) -> {
            haxe.Timer.delay(() -> {
                resolve(user.process());
            }, 1000);
        });
    }
    
    // Function using abstract type
    static function validateAge(age:Age):Bool {
        return age.isAdult();
    }
    
    // Main function
    static public function main():Void {
        // Create users
        var user1 = new User("John", 25);
        var user2 = new User("Alice", 17);
        var users = [user1, user2];
        
        // Test basic functions
        trace("Users:");
        for (user in users) {
            trace(user.format());
        }
        
        // Test processing
        var processor = new UserProcessor();
        trace("\nProcessing results:");
        var results = processor.processUsers(users);
        for (result in results) {
            trace(result.message);
        }
        
        // Test user finding
        trace("\nFinding user:");
        var foundUser = findUser(users, "John");
        if (foundUser != null) {
            trace('Found: ${foundUser.format()}');
        }
        
        // Test abstract type
        trace("\nAge validation:");
        var age:Age = 20;
        trace('Is adult? ${validateAge(age)}');
        
        // Test generic collection
        trace("\nGeneric collection:");
        var collection = new UserCollection();
        collection.add(user1);
        collection.add(user2);
        for (user in collection.getUsers()) {
            trace(user.format(true));
        }
        
        // Test async processing
        processUserAsync(user1).then(result -> {
            trace('\nAsync result: ${result.message}');
        });
        
        // Test greetings
        trace("\nGreetings:");
        trace(createGreeting(name = "Bob"));
        trace(createGreeting("Hi", "Charlie"));
    }
} 