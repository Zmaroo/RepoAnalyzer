function greet(name) {
    return `Hello, ${name}!`;
}

class UserService {
    constructor() {
        this.users = [];
    }
    
    addUser(user) {
        this.users.push(user);
    }
}

// Handler function
const handler = function() {
    return function(data) {
        return data.process();
    }
};

// Process arrow function with nested arrow function
const process = (input) => {
    return input.map(x => x * 2);
}; 