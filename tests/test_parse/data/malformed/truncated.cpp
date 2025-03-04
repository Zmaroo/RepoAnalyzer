#include <iostream>
#include <string>

class TruncatedClass {
public:
    TruncatedClass() {
        // Constructor implementation
        std::cout << "Constructor called" << std::endl;
    }
    
    void truncatedMethod() {
        std::string str = "This method is truncated";
        
        for (int i = 0; i < 10; i++) {
            // This loop is truncated
            std::cout << "Iteration " << i << std::endl;
        }
    }
}; 