-- Regular function
function add(a, b)
    return a + b
end

-- Local function
local function subtract(a, b)
    return a - b
end

-- Anonymous function assigned to variable
local multiply = function(a, b)
    return a * b
end

-- Function with multiple returns
function divmod(a, b)
    return math.floor(a/b), a % b
end

-- Function with variable arguments
function sum(...)
    local result = 0
    for _, v in ipairs({...}) do
        result = result + v
    end
    return result
end

-- Table with methods
local Calculator = {
    value = 0,
    
    -- Method using colon syntax
    add = function(self, x)
        self.value = self.value + x
    end,
    
    -- Alternative method syntax
    subtract = function(self, x)
        self.value = self.value - x
    end
}

-- Method using colon syntax (syntactic sugar)
function Calculator:multiply(x)
    self.value = self.value * x
end

-- Class-like structure with constructor
local function createPerson(name)
    local person = {
        name = name,
        
        -- Method
        greet = function(self)
            return "Hello, I'm " .. self.name
        end
    }
    
    -- Return the instance
    return person
end

-- Closure example
function counter()
    local count = 0
    return function()
        count = count + 1
        return count
    end
end

-- Function that returns multiple functions
function makeOperations()
    return function(x) return x + 1 end,
           function(x) return x - 1 end
end

-- Main execution
local function main()
    -- Test regular function
    print(add(5, 3))
    
    -- Test calculator
    Calculator:add(10)
    print(Calculator.value)
    
    -- Test person
    local person = createPerson("Alice")
    print(person:greet())
    
    -- Test counter
    local count = counter()
    print(count())
    print(count())
end

-- Call main
main() 