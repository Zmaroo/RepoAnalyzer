// Test file for JavaScript semantics pattern detection

// Class definition with static members and private fields
class Example {
    static version = '1.0.0';
    #privateField = 'private';
    
    constructor() {
        this.publicField = 'public';
    }
    
    static {
        Example.initialized = true;
    }
}

// Async/await patterns
async function fetchData() {
    try {
        const response = await fetch('https://api.example.com/data');
        return await response.json();
    } catch (error) {
        console.error('Error:', error);
    }
}

// Generator functions
function* numberGenerator() {
    yield 1;
    yield* [2, 3, 4];
    yield 5;
}

// Destructuring patterns
const { a, b, ...rest } = { a: 1, b: 2, c: 3, d: 4 };
const [first, second, ...remaining] = [1, 2, 3, 4, 5];

// Arrow functions with different patterns
const arrowFunc = () => 'simple return';
const multiLine = () => {
    const x = 1;
    return x + 2;
};
const immediate = (() => 'IIFE')();

// Promises and chaining
new Promise((resolve, reject) => {
    resolve('success');
})
    .then(result => result.toUpperCase())
    .catch(error => console.error(error))
    .finally(() => console.log('done'));

// Object patterns
const proto = {
    shared: 'method'
};

const obj = {
    prop: 'value',
    method() {
        return this.prop;
    },
    get computed() {
        return this._computed;
    },
    set computed(value) {
        this._computed = value;
    },
    __proto__: proto
};

// Function patterns
function defaultParams(a = 1, b = 2) {
    return a + b;
}

function restParams(...args) {
    return args.reduce((sum, curr) => sum + curr, 0);
}

// Module patterns
export const exported = 'I am exported';
export default class DefaultExport {
    constructor() {
        this.name = 'default';
    }
}

// Proxy pattern
const handler = {
    get: function(target, prop) {
        return prop in target ? target[prop] : 'default';
    }
};
const proxy = new Proxy({}, handler);

// Symbol usage
const symbol = Symbol('description');
const obj2 = {
    [symbol]: 'symbol value'
}; 