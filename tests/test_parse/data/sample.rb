# Regular method
def add(a, b)
  a + b
end

# Method with default parameter
def greet(name = "World")
  puts "Hello, #{name}!"
end

# Method with keyword arguments
def create_user(name:, age:, email: nil)
  { name: name, age: age, email: email }
end

# Method with block parameter
def execute_block
  yield if block_given?
end

# Class method
class Calculator
  def self.add(a, b)
    a + b
  end
  
  # Instance method
  def multiply(a, b)
    a * b
  end
  
  # Private method
  private
  
  def validate(num)
    num.is_a?(Numeric)
  end
end

# Module with included methods
module Greeting
  def say_hello
    "Hello!"
  end
  
  module_function
  
  def say_goodbye
    "Goodbye!"
  end
end

# Class with mixed in module
class Person
  include Greeting
  
  def initialize(name)
    @name = name
  end
  
  # Getter method
  attr_reader :name
  
  # Method with block
  def do_something
    yield(@name) if block_given?
  end
end

# Lambda (proc)
multiply = ->(x, y) { x * y }

# Proc
divide = Proc.new { |x, y| x / y }

# Method with splat operator
def sum(*numbers)
  numbers.reduce(0, :+)
end

# Main execution
if __FILE__ == $PROGRAM_NAME
  calculator = Calculator.new
  puts calculator.multiply(5, 3)
end 