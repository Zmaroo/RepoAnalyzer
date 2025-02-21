#include <iostream>
#include <vector>
#include <functional>

// Regular function
int add(int a, int b) {
    return a + b;
}

// Function template
template<typename T>
T maximum(T a, T b) {
    return (a > b) ? a : b;
}

// Lambda function
auto multiply = [](int x, int y) { return x * y; };

// Class with member functions
class Calculator {
public:
    // Constructor
    Calculator() = default;
    
    // Destructor
    ~Calculator() {}
    
    // Regular method
    int subtract(int a, int b) const {
        return a - b;
    }
    
    // Static method
    static double divide(double a, double b) {
        return a / b;
    }
    
    // Operator overload
    Calculator operator+(const Calculator& other) {
        return *this;
    }
    
    // Template method
    template<typename T>
    T power(T base, int exp) {
        T result = 1;
        for(int i = 0; i < exp; ++i) {
            result *= base;
        }
        return result;
    }

private:
    // Virtual method
    virtual void update() {}
};

// Derived class with override
class AdvancedCalculator : public Calculator {
public:
    // Override virtual function
    void display() override {
        std::cout << "Advanced Calculator Value: " << getValue() << std::endl;
    }
};

// Function with reference parameter
void increment(int& x) {
    x++;
}

// Function with default arguments
void print(std::string message = "Hello") {
    std::cout << message << std::endl;
}

// Function returning lambda
auto get_multiplier(int factor) {
    return [factor](int x) { return x * factor; };
}

// Namespace with functions
namespace Math {
    double square(double x) {
        return x * x;
    }

    namespace Advanced {
        double cube(double x) {
            return x * x * x;
        }
    }
}

// Function with lambda
void process(int x) {
    // Lambda expression
    auto square = [](int n) -> int { 
        return n * n; 
    };
    
    // Lambda with capture
    int multiplier = 2;
    auto multiply = [multiplier](int n) {
        return n * multiplier;
    };
}

// Function with noexcept
void safeOperation() noexcept {
    // Implementation
}

// Function with constexpr
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

// Function with trailing return type
auto getSum(int a, int b) -> int {
    return a + b;
}

// Variadic template function
template<typename... Args>
int sum(Args... args) {
    return (... + args);
}

// Friend function
class Box {
    friend void printBox(const Box& b);
    int width = 0;
};

void printBox(const Box& b) {
    std::cout << b.width;
}

// Main function
int main() {
    Calculator calc;
    calc.add(5);
    return 0;
} 