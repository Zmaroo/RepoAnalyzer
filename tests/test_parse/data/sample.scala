// Regular function
def add(a: Int, b: Int): Int = a + b

// Function with type parameter
def identity[T](x: T): T = x

// Multi-parameter list function
def curriedAdd(x: Int)(y: Int): Int = x + y

// Function with default parameter
def greet(name: String = "World"): String = s"Hello, $name!"

// Case class with methods
case class Person(name: String, age: Int) {
  def greet(): String = s"Hello, my name is $name"
  def birthday(): Person = copy(age = age + 1)
}

// Trait with abstract and concrete methods
trait Animal {
  def speak(): String
  def move(): String = "Moving..."
}

// Class implementing trait
class Dog(name: String) extends Animal {
  def speak(): String = "Woof!"
  override def move(): String = "Running on four legs"
}

// Object with singleton methods
object MathUtils {
  def square(x: Int): Int = x * x
  def cube(x: Int): Int = x * x * x
}

// Higher-order function
def applyTwice(f: Int => Int, x: Int): Int = f(f(x))

// Anonymous function (lambda)
val multiply = (x: Int, y: Int) => x * y

// Partial function
val divide: PartialFunction[Int, Int] = {
  case x if x != 0 => 100 / x
}

// Function with implicit parameters
def printWithContext(message: String)(implicit ctx: String): Unit =
  println(s"[$ctx] $message")

// Main object
object Main extends App {
  val person = Person("Alice", 30)
  println(person.greet())
  
  implicit val context: String = "DEBUG"
  printWithContext("Test message")
} 