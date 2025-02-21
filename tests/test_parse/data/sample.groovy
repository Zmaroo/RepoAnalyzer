// User class with various method types
class User {
    String name
    int age
    
    // Constructor
    User(String name, int age) {
        this.name = name
        this.age = age
    }
    
    // Method with default parameter
    def greet(String prefix = "Hello") {
        "$prefix, $name!"
    }
    
    // Method using safe navigation
    def getDescription() {
        "${name?.capitalize()} (${age} years old)"
    }
    
    // Method with type checking
    boolean isAdult() {
        assert age >= 0
        age >= 18
    }
    
    // Operator overloading
    User plus(User other) {
        new User(name + " & " + other.name, Math.max(age, other.age))
    }
    
    // toString override
    String toString() {
        getDescription()
    }
}

// Trait definition
trait Processable {
    abstract def process()
    
    def validate() {
        true
    }
}

// Class implementing trait
class ProcessableUser extends User implements Processable {
    ProcessableUser(String name, int age) {
        super(name, age)
    }
    
    def process() {
        "Processing user: $name"
    }
}

// Closure example
def userProcessor = { User user ->
    println "Processing ${user.name}..."
    user.isAdult() ? "Adult user" : "Minor user"
}

// Function with multiple return values
def getUserStats(List<User> users) {
    def adultCount = users.count { it.isAdult() }
    def averageAge = users.sum { it.age } / users.size()
    [adultCount: adultCount, averageAge: averageAge]
}

// Extension method
User.metaClass.getUppercaseName = {
    delegate.name.toUpperCase()
}

// Function using spread operator
def processUsers(List<User> users) {
    users*.process()
}

// Function with type coercion
def formatAge(age) {
    age as String + " years old"
}

// Curried function
def createGreeting = { String prefix ->
    { String name ->
        "$prefix, $name!"
    }
}

// Main execution
def runExample() {
    // Create users
    def user1 = new ProcessableUser("John", 25)
    def user2 = new ProcessableUser("Alice", 17)
    def users = [user1, user2]
    
    // Test basic methods
    println "Users:"
    users.each { println it }
    
    // Test closure
    println "\nProcessing results:"
    users.each { println userProcessor(it) }
    
    // Test statistics
    def stats = getUserStats(users)
    println "\nStats:"
    println "Adult count: ${stats.adultCount}"
    println "Average age: ${stats.averageAge}"
    
    // Test extension method
    println "\nUppercase names:"
    users.each { println it.uppercaseName }
    
    // Test operator overloading
    def combinedUser = user1 + user2
    println "\nCombined user: $combinedUser"
    
    // Test curried function
    def sayHello = createGreeting("Hello")
    def sayHi = createGreeting("Hi")
    println "\nGreetings:"
    println sayHello("Bob")
    println sayHi("Charlie")
    
    // Test processable interface
    println "\nProcessing users:"
    processUsers(users).each { println it }
}

// Run the example
runExample() 