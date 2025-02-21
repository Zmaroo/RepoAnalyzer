<?php
// Sample PHP code with various function types

// Class definition with different method types
class User {
    private string $name;
    private int $age;
    
    public function __construct(string $name, int $age) {
        $this->name = $name;
        $this->age = $age;
    }
    
    // Regular method
    public function getName(): string {
        return $this->name;
    }
    
    // Method with type hints
    public function setAge(int $age): void {
        $this->age = $age;
    }
    
    // Static method
    public static function fromArray(array $data): User {
        return new self($data['name'], $data['age']);
    }
    
    // Method with nullable return type
    public function getDescription(): ?string {
        if ($this->age < 18) {
            return null;
        }
        return "{$this->name} is {$this->age} years old";
    }
    
    // Abstract method example (would be in abstract class)
    // abstract protected function validate(): bool;
}

// Interface example
interface UserRepository {
    public function save(User $user): void;
    public function find(int $id): ?User;
}

// Trait with method
trait Loggable {
    private function log(string $message): void {
        echo "[LOG] {$message}\n";
    }
}

// Regular function
function greet(string $name): string {
    return "Hello, {$name}!";
}

// Function with default parameter
function multiply(int $a, int $b = 2): int {
    return $a * $b;
}

// Function with variadic parameters
function sum(...$numbers): int {
    return array_sum($numbers);
}

// Arrow function (PHP 7.4+)
$double = fn($x) => $x * 2;

// Anonymous function
$filter = function(array $items, callable $predicate) {
    return array_filter($items, $predicate);
};

// Closure with 'use'
$multiplier = 3;
$triple = function($x) use ($multiplier) {
    return $x * $multiplier;
};

// Main execution
$user = new User("John", 25);
echo greet($user->getName()) . "\n";

$numbers = [1, 2, 3, 4, 5];
echo "Double of 5: " . $double(5) . "\n";
echo "Sum of numbers: " . sum(...$numbers) . "\n";

$evenNumbers = $filter($numbers, fn($n) => $n % 2 === 0);
print_r($evenNumbers);

echo "Triple of 4: " . $triple(4) . "\n"; 