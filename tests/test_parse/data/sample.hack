<?hh // strict

namespace UserManager;

// Type aliases
type UserMap = Map<string, User>;
type ProcessResult = shape(
    'success' => bool,
    'message' => string,
);

// Interface definition
interface Processable {
    public function process(): ProcessResult;
}

// Class definition
class User implements Processable {
    private string $name;
    private int $age;
    
    // Constructor
    public function __construct(string $name, int $age) {
        $this->name = $name;
        $this->age = $age;
    }
    
    // Getter methods
    public function getName(): string {
        return $this->name;
    }
    
    public function getAge(): int {
        return $this->age;
    }
    
    // Implementation of interface method
    public function process(): ProcessResult {
        return shape(
            'success' => $this->age >= 18,
            'message' => $this->age >= 18 ? 'Adult user' : 'Minor user'
        );
    }
    
    // Method with type hints
    public function format(bool $verbose = false): string {
        return $verbose
            ? sprintf("%s is %d years old", $this->name, $this->age)
            : sprintf("%s (%d)", $this->name, $this->age);
    }
}

// Generic class
class UserCollection<T as User> {
    private Vector<T> $users;
    
    public function __construct() {
        $this->users = new Vector();
    }
    
    public function add(T $user): void {
        $this->users->add($user);
    }
    
    public function getUsers(): Vector<T> {
        return $this->users;
    }
}

// Function with type parameters
function processUsers<T as User>(Vector<T> $users): Vector<ProcessResult> {
    return $users->map($user ==> $user->process());
}

// Function with nullable return
function findUser(UserMap $users, string $name): ?User {
    return $users->get($name);
}

// Async function
async function processUserAsync(User $user): Awaitable<ProcessResult> {
    await async_sleep(1);
    return $user->process();
}

// Function returning tuple
function getUserStats(Vector<User> $users): (int, float) {
    $total = $users->count();
    if ($total === 0) {
        return tuple(0, 0.0);
    }
    
    $adultCount = $users->filter($user ==> $user->getAge() >= 18)->count();
    $averageAge = $users->map($user ==> $user->getAge())->reduce(
        ($acc, $age) ==> $acc + $age,
        0
    ) / $total;
    
    return tuple($adultCount, $averageAge);
}

// Main execution function
async function run(): Awaitable<void> {
    // Create users
    $user1 = new User("John", 25);
    $user2 = new User("Alice", 17);
    
    $users = new Vector([$user1, $user2]);
    $userMap = Map {
        "John" => $user1,
        "Alice" => $user2
    };
    
    // Test basic functions
    echo "Users:\n";
    foreach ($users as $user) {
        echo $user->format() . "\n";
    }
    
    // Test processing
    echo "\nProcessing results:\n";
    $results = processUsers($users);
    foreach ($results as $result) {
        echo $result['message'] . "\n";
    }
    
    // Test async processing
    echo "\nAsync processing:\n";
    $asyncResult = await processUserAsync($user1);
    echo "Async result: " . $asyncResult['message'] . "\n";
    
    // Test user finding
    echo "\nFinding user:\n";
    $foundUser = findUser($userMap, "John");
    if ($foundUser !== null) {
        echo "Found: " . $foundUser->format() . "\n";
    }
    
    // Test statistics
    list($adultCount, $averageAge) = getUserStats($users);
    echo "\nStats:\n";
    echo "Adult count: $adultCount\n";
    echo "Average age: $averageAge\n";
    
    // Test generic collection
    echo "\nGeneric collection:\n";
    $collection = new UserCollection();
    $collection->add($user1);
    $collection->add($user2);
    foreach ($collection->getUsers() as $user) {
        echo $user->format(true) . "\n";
    }
}

// Run the example
\HH\Asio\join(run()); 