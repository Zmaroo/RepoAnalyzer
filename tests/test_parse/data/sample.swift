// Regular function
func add(_ a: Int, _ b: Int) -> Int {
    return a + b
}

// Function with default parameter
func greet(name: String = "World") -> String {
    return "Hello, \(name)!"
}

// Function with multiple return values
func minMax(array: [Int]) -> (min: Int, max: Int)? {
    guard !array.isEmpty else { return nil }
    return (array.min()!, array.max()!)
}

// Function with variadic parameters
func sum(_ numbers: Int...) -> Int {
    return numbers.reduce(0, +)
}

// Function with inout parameter
func swapValues(_ a: inout Int, _ b: inout Int) {
    let temp = a
    a = b
    b = temp
}

// Generic function
func swap<T>(_ a: inout T, _ b: inout T) {
    let temp = a
    a = b
    b = temp
}

// Closure expression
let multiply: (Int, Int) -> Int = { (a, b) in
    return a * b
}

// Class with methods
class Calculator {
    var value: Int = 0
    
    // Instance method
    func add(_ x: Int) {
        value += x
    }
    
    // Type method (static)
    static func multiply(_ a: Int, _ b: Int) -> Int {
        return a * b
    }
    
    // Mutating method
    func reset() {
        value = 0
    }
}

// Protocol with function requirements
protocol Animal {
    func makeSound() -> String
    func move()
}

// Class conforming to protocol
class Dog: Animal {
    func makeSound() -> String {
        return "Woof!"
    }
    
    func move() {
        print("Running on four legs")
    }
}

// Extension with added functionality
extension Int {
    func squared() -> Int {
        return self * self
    }
}

// Async function
func fetchData() async throws -> String {
    return "Data"
}

// Main execution
@main
struct MainProgram {
    static func main() {
        let result = add(5, 3)
        print("Result: \(result)")
    }
} 