# Regular function
add <- function(a, b) {
  a + b
}

# Function with default arguments
greet <- function(name = "World") {
  paste("Hello,", name, "!")
}

# Function returning multiple values
get_stats <- function(x) {
  list(
    mean = mean(x),
    median = median(x),
    sd = sd(x)
  )
}

# Function with variable arguments
sum_all <- function(...) {
  args <- list(...)
  sum(unlist(args))
}

# Function with formula
regression <- function(formula, data) {
  lm(formula, data = data)
}

# Anonymous function
lapply(1:3, function(x) x^2)

# Closure
make_counter <- function() {
  count <- 0
  function() {
    count <<- count + 1
    count
  }
}

# S3 class and methods
make_person <- function(name, age) {
  structure(
    list(
      name = name,
      age = age
    ),
    class = "person"
  )
}

print.person <- function(x, ...) {
  cat("Person:", x$name, "\n")
  cat("Age:", x$age, "\n")
}

# S4 class and methods
setClass(
  "Calculator",
  slots = list(
    value = "numeric"
  )
)

setMethod(
  "show",
  "Calculator",
  function(object) {
    cat("Calculator value:", object@value, "\n")
  }
)

setGeneric("add_value", function(obj, x) standardGeneric("add_value"))

setMethod(
  "add_value",
  "Calculator",
  function(obj, x) {
    obj@value <- obj@value + x
    obj
  }
)

# Function with attributes
weighted_mean <- function(x, w) {
  sum(x * w) / sum(w)
}
attr(weighted_mean, "description") <- "Calculates weighted mean"

# Main execution
main <- function() {
  # Test regular function
  result <- add(5, 3)
  print(result)
  
  # Test person class
  person <- make_person("Alice", 30)
  print(person)
  
  # Test calculator
  calc <- new("Calculator", value = 0)
  calc <- add_value(calc, 10)
  show(calc)
}

# Run main
main() 