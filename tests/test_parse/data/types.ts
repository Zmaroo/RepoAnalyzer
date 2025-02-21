interface User {
    id: number;
    name: string;
}

class UserManager {
    private users: User[] = [];
    
    public addUser(user: User): void {
        this.users.push(user);
    }

    private process = (data: User[]): User[] => {
        return data.map((user: User) => {
            return { ...user, id: user.id + 1 };
        });
    }

    private transform = function(user: User): User {
        return { ...user, name: user.name.toUpperCase() };
    }
}

// Interface with method signatures
interface Calculator {
    add(a: number, b: number): number;
    subtract(a: number, b: number): number;
}

// Regular function
function regularFunction(): string {
    return "Hello";
}

// Arrow function
const arrowFunction = (name: string): string => {
    return `Hello ${name}`;
};

// Async function
async function asyncFunction(): Promise<string> {
    return "async result";
}

// Generic function
function genericFunction<T>(arg: T): T {
    return arg;
}

// Function with optional parameters
function optionalParams(required: string, optional?: number): string {
    return `${required} ${optional || ''}`;
}

// Function with rest parameters
function restParams(...numbers: number[]): number {
    return numbers.reduce((a, b) => a + b, 0);
}

// Class with various method types
class TestClass {
    private value: number;

    constructor() {
        this.value = 42;
    }

    // Instance method
    public instanceMethod(): number {
        return this.value;
    }

    // Private method
    private privateMethod(): void {
        console.log("private");
    }

    // Static method
    static staticMethod(): string {
        return "static";
    }

    // Getter
    get valueGetter(): number {
        return this.value;
    }

    // Setter
    set valueSetter(v: number) {
        this.value = v;
    }

    // Async method
    async asyncMethod(): Promise<number> {
        return this.value;
    }
}

// Abstract class with abstract methods
abstract class AbstractClass {
    abstract abstractMethod(): void;

    concreteMethod(): string {
        return "concrete";
    }
}

// Function type with implementation
type FunctionType = (x: number) => number;
const implementedFunction: FunctionType = (x) => x * 2;

// Overloaded function
function overloaded(x: string): string;
function overloaded(x: number): number;
function overloaded(x: any): any {
    return x;
}

// Generator function
function* generatorFunction(): Generator<number> {
    yield 1;
    yield 2;
}

// Async generator function
async function* asyncGeneratorFunction(): AsyncGenerator<number> {
    yield 1;
    yield 2;
} 