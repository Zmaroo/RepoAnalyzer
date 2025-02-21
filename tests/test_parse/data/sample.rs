// Regular function
fn add(a: i32, b: i32) -> i32 {
    a + b
}

// Function with generic type
fn print_value<T: std::fmt::Display>(value: T) {
    println!("{}", value);
}

// Async function
async fn fetch_data() -> Result<String, std::io::Error> {
    Ok(String::from("data"))
}

// Function with lifetime parameter
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}

// Trait definition with function
trait Animal {
    fn make_sound(&self) -> String;
    
    fn default_behavior(&self) -> String {
        String::from("some default behavior")
    }
}

// Struct with implementation
struct Dog {
    name: String,
}

impl Dog {
    // Associated function (static method)
    fn new(name: String) -> Dog {
        Dog { name }
    }
    
    // Method
    fn bark(&self) -> String {
        format!("{} says: Woof!", self.name)
    }
}

// Implement trait for struct
impl Animal for Dog {
    fn make_sound(&self) -> String {
        self.bark()
    }
}

// Closure (lambda)
let multiply = |x: i32, y: i32| x * y;

// Function that takes a closure
fn apply_operation<F>(x: i32, y: i32, operation: F) -> i32 
where F: Fn(i32, i32) -> i32 
{
    operation(x, y)
}

// Main function
fn main() {
    let result = add(5, 3);
    println!("Result: {}", result);
    
    let dog = Dog::new(String::from("Rover"));
    println!("{}", dog.bark());
} 