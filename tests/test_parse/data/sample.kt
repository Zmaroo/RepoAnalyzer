// Top-level function
fun add(a: Int, b: Int): Int = a + b

// Function with default parameters
fun greet(name: String = "World") = "Hello, $name!"

// Function with multiple parameters
fun createUser(name: String, age: Int, email: String? = null) =
    mapOf("name" to name, "age" to age, "email" to email)

// Extension function
fun String.addExclamation() = "$this!"

// Infix function
infix fun Int.times(str: String) = str.repeat(this)

// Operator function
operator fun Int.plus(other: Int) = this + other

// Higher-order function
fun operation(x: Int, y: Int, op: (Int, Int) -> Int): Int = op(x, y)

// Lambda expression
val multiply = { x: Int, y: Int -> x * y }

// Suspend function
suspend fun fetchData(): String {
    return "Data"
}

// Class with different function types
class Calculator {
    private var value: Int = 0

    // Member function
    fun add(x: Int) {
        value += x
    }

    // Property with custom getter
    val current: Int
        get() = value

    // Companion object function (static)
    companion object {
        fun multiply(x: Int, y: Int) = x * y
    }
}

// Interface with function
interface Animal {
    fun makeSound(): String
    fun move() {
        println("Moving...")
    }
}

// Class implementing interface
class Dog : Animal {
    override fun makeSound() = "Woof!"
}

// Data class with functions
data class Person(val name: String, var age: Int) {
    fun birthday() {
        age++
    }
}

// Generic function
fun <T> printArray(array: Array<T>) {
    array.forEach { println(it) }
}

// Function with receiver
fun Int.squared(): Int = this * this

// Scope function
fun processPerson(person: Person) {
    person.apply {
        age += 1
        println("Happy birthday, $name!")
    }
}

// Main function
fun main() {
    val result = add(5, 3)
    println("Result: $result")

    val person = Person("Alice", 30)
    processPerson(person)
} 