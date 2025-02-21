import gleam/io
import gleam/int
import gleam/list
import gleam/option.{Option, None, Some}
import gleam/result.{Result, Ok, Error}
import gleam/string

// Type definitions
pub type User {
  User(name: String, age: Int)
}

pub type ProcessResult {
  Success(message: String)
  Failure(error: String)
}

// Type alias
pub type Name = String
pub type Age = Int
pub type Users = List(User)

// Function to create a user with validation
pub fn create_user(name: Name, age: Age) -> Result(User, String) {
  case age {
    age if age < 0 -> Error("Age cannot be negative")
    age if age > 150 -> Error("Age cannot be greater than 150")
    _ -> Ok(User(name, age))
  }
}

// Function with pattern matching
pub fn process_user(user: User) -> ProcessResult {
  case user {
    User(_, age) if age < 0 -> Failure("Invalid age")
    User(_, age) if age < 18 -> Failure("Underage")
    User(name, _) -> Success("Processing adult user: " <> name)
  }
}

// Function with default parameter using option
pub fn create_greeting(name: String, prefix: Option(String)) -> String {
  let actual_prefix = option.unwrap(prefix, "Hello")
  actual_prefix <> ", " <> name <> "!"
}

// Function returning multiple values using tuple
pub fn get_user_stats(users: Users) -> #(Int, Int) {
  let total = list.length(users)
  let adults = users
    |> list.filter(is_adult)
    |> list.length()
  #(total, adults)
}

// Function using pipe operator
pub fn format_user(user: User) -> String {
  case user {
    User(name, age) -> 
      name
      |> string.append(" (")
      |> string.append(int.to_string(age))
      |> string.append(" years old)")
  }
}

// Higher order function
pub fn process_users(users: Users, processor: fn(User) -> String) -> List(String) {
  list.map(users, processor)
}

// Function returning function (closure)
pub fn create_age_checker(min_age: Int) -> fn(User) -> Bool {
  fn(user: User) -> Bool {
    case user {
      User(_, age) -> age >= min_age
    }
  }
}

// Function using list comprehension and pattern matching
pub fn find_user(users: Users, name: String) -> Option(User) {
  users
  |> list.find(fn(user) {
    case user {
      User(n, _) -> n == name
    }
  })
}

// Private helper function
fn is_adult(user: User) -> Bool {
  case user {
    User(_, age) -> age >= 18
  }
}

// Function using Result for error handling
pub fn validate_user(user: User) -> Result(User, String) {
  case user {
    User(name, age) if string.length(name) == 0 -> 
      Error("Name cannot be empty")
    User(_, age) if age < 0 -> 
      Error("Age cannot be negative")
    user -> 
      Ok(user)
  }
}

// Function using list operations
pub fn get_adult_users(users: Users) -> Users {
  list.filter(users, is_adult)
}

// Function using string manipulation
pub fn process_name(name: String) -> String {
  name
  |> string.trim()
  |> string.lowercase
  |> string.capitalise
}

// Main function to demonstrate usage
pub fn main() {
  // Create users
  let user1 = create_user("John", 25)
  let user2 = create_user("Alice", 17)
  
  case #(user1, user2) {
    #(Ok(u1), Ok(u2)) -> {
      let users = [u1, u2]
      
      // Test basic functions
      io.println("Users:")
      users
      |> list.map(format_user)
      |> list.each(io.println)
      
      // Test processing
      io.println("\nProcessing results:")
      users
      |> list.map(process_user)
      |> list.each(fn(result) {
        case result {
          Success(msg) -> io.println(msg)
          Failure(err) -> io.println("Error: " <> err)
        }
      })
      
      // Test user stats
      let #(total, adults) = get_user_stats(users)
      io.println("\nStats:")
      io.println("Total users: " <> int.to_string(total))
      io.println("Adult users: " <> int.to_string(adults))
      
      // Test user finding
      io.println("\nFinding user:")
      case find_user(users, "John") {
        Some(user) -> io.println("Found: " <> format_user(user))
        None -> io.println("User not found")
      }
      
      // Test age checker
      let is_adult = create_age_checker(18)
      io.println("\nAge check:")
      users
      |> list.map(fn(user) {
        case user {
          User(name, _) if is_adult(user) -> 
            name <> " is an adult"
          User(name, _) -> 
            name <> " is not an adult"
        }
      })
      |> list.each(io.println)
      
      // Test validation
      io.println("\nValidation:")
      users
      |> list.map(validate_user)
      |> list.each(fn(result) {
        case result {
          Ok(_) -> io.println("User is valid")
          Error(msg) -> io.println("Validation error: " <> msg)
        }
      })
      
      // Test name processing
      io.println("\nProcessed names:")
      users
      |> list.map(fn(user) {
        case user {
          User(name, _) -> process_name(name)
        }
      })
      |> list.each(io.println)
    }
    
    #(Error(e1), _) -> io.println("Error creating user1: " <> e1)
    #(_, Error(e2)) -> io.println("Error creating user2: " <> e2)
  }
} 