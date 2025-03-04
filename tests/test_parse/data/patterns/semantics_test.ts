// Test file for semantics pattern detection

// Type assertions
let someValue: any = "this is a string";
let strLength: number = (someValue as string).length;
let otherLength: number = (<string>someValue).length;

// Type predicates
function isString(test: any): test is string {
    return typeof test === "string";
}

// Type queries
type Constructor = typeof String;
type ReturnType = ReturnType<typeof isString>;

// Union types
type StringOrNumber = string | number;
type Status = "success" | "error" | "pending";

// Intersection types
interface Named {
    name: string;
}
interface Aged {
    age: number;
}
type Person = Named & Aged;

// Tuple types
let tuple: [string, number] = ["hello", 10];
type StringNumberBooleans = [string, number, ...boolean[]];

// Variables with different types
const constVar = "I'm constant";
let letVar = "I can change";
var oldVar = "Old style";

// Complex types
type ComplexType = {
    name: string;
    age: number;
    contact: {
        email: string;
        phone?: string;
    };
    roles: string[];
};

// Parameters with types
function processData(
    data: any,
    callback: (error: Error | null, result?: any) => void
): void {
    // Implementation
}

// Return types
function getData(): Promise<ComplexType> {
    return Promise.resolve({
        name: "Test",
        age: 30,
        contact: { email: "test@test.com" },
        roles: ["user"]
    });
}

// Generics
class Container<T> {
    private value: T;
    
    constructor(value: T) {
        this.value = value;
    }
    
    getValue(): T {
        return this.value;
    }
}

// Template literal types
type EventName<T extends string> = `${T}Event`;
type MouseEvents = EventName<"click" | "mousedown" | "mouseup">;

// Operators
const sum = (a: number, b: number): number => a + b;
const product = (a: number, b: number): number => a * b;
const comparison = (a: number, b: number): boolean => a > b; 