#include <iostream>
#include <memory>
#include <vector>
#include <type_traits>

// Template metaprogramming patterns
template<typename T>
struct is_pointer_custom {
    static constexpr bool value = false;
};

template<typename T>
struct is_pointer_custom<T*> {
    static constexpr bool value = true;
};

// CRTP pattern
template<typename Derived>
class Base {
public:
    void interface() {
        static_cast<Derived*>(this)->implementation();
    }
};

class Derived : public Base<Derived> {
public:
    void implementation() {
        std::cout << "Derived implementation\n";
    }
};

// Smart pointer usage
class Resource {
public:
    Resource() = default;
    void use() { std::cout << "Using resource\n"; }
};

// Multiple inheritance and virtual functions
class Interface1 {
public:
    virtual ~Interface1() = default;
    virtual void method1() = 0;
};

class Interface2 {
public:
    virtual ~Interface2() = default;
    virtual void method2() = 0;
};

class Implementation : public Interface1, public Interface2 {
public:
    void method1() override { std::cout << "Method 1\n"; }
    void method2() override { std::cout << "Method 2\n"; }
};

// Template specialization
template<typename T>
class Container {
public:
    void store(T value) { data = value; }
private:
    T data;
};

template<>
class Container<bool> {
public:
    void store(bool value) { data = value; }
private:
    bool data : 1;
};

// Operator overloading
class Complex {
public:
    Complex(double r = 0, double i = 0) : real(r), imag(i) {}
    
    Complex operator+(const Complex& other) const {
        return Complex(real + other.real, imag + other.imag);
    }
    
    friend std::ostream& operator<<(std::ostream& os, const Complex& c) {
        return os << c.real << " + " << c.imag << "i";
    }
    
private:
    double real, imag;
};

// Type traits and concepts (C++20)
template<typename T>
concept Numeric = std::is_arithmetic_v<T>;

template<Numeric T>
T add(T a, T b) {
    return a + b;
}

// RAII pattern
class ScopedResource {
public:
    ScopedResource() { std::cout << "Resource acquired\n"; }
    ~ScopedResource() { std::cout << "Resource released\n"; }
};

int main() {
    // Smart pointer demonstration
    auto resource = std::make_unique<Resource>();
    resource->use();
    
    // CRTP demonstration
    Derived d;
    d.interface();
    
    // Multiple inheritance demonstration
    Implementation impl;
    impl.method1();
    impl.method2();
    
    // Template and operator overloading demonstration
    Complex c1(1, 2), c2(3, 4);
    std::cout << c1 + c2 << std::endl;
    
    // RAII demonstration
    {
        ScopedResource sr;
    } // Resource automatically released here
    
    return 0;
} 