// Sample Dart code with various function types
class User {
  String name;
  int age;

  User(this.name, this.age);

  // Regular method
  void printInfo() {
    print('Name: $name, Age: $age');
  }

  // Method with return type and parameters
  bool isAdult(int minAge) {
    return age >= minAge;
  }

  // Getter method
  String get info => '$name ($age years old)';

  // Static method
  static User fromMap(Map<String, dynamic> map) {
    return User(map['name'], map['age']);
  }
}

// Top-level function
void greet(String name) {
  print('Hello, $name!');
}

// Function with optional parameters
String formatName(String firstName, [String? lastName]) {
  return lastName != null ? '$firstName $lastName' : firstName;
}

// Function with named parameters
void createUser({required String name, int age = 0}) {
  final user = User(name, age);
  user.printInfo();
}

// Arrow function
int add(int a, int b) => a + b;

void main() {
  // Anonymous function
  final multiply = (int x, int y) {
    return x * y;
  };

  final user = User('John', 25);
  user.printInfo();
  
  greet('Alice');
  
  print(add(5, 3));
  print(multiply(4, 2));
  
  createUser(name: 'Bob', age: 30);
} 