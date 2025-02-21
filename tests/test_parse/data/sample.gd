extends Node

# Sample GDScript file demonstrating various function types

# Built-in virtual functions
func _ready():
    print("Node is ready")
    _test_functions()

func _process(delta):
    # Called every frame
    pass

func _input(event):
    if event is InputEventKey:
        _handle_input(event)

# Regular function with parameters and return type
func calculate_damage(base_damage: float, multiplier: float) -> float:
    return base_damage * multiplier

# Function with default parameters
func spawn_enemy(position: Vector2 = Vector2.ZERO, health: int = 100) -> void:
    print("Spawning enemy at ", position, " with health ", health)

# Function with typed parameters
func move_character(direction: Vector2, speed: float) -> void:
    position += direction * speed

# Static function (using static keyword)
static func create_instance() -> Node:
    return Node.new()

# Private function (convention: starts with underscore)
func _handle_input(event: InputEventKey) -> void:
    if event.pressed:
        print("Key pressed: ", event.scancode)

# Async function
func _load_resource(path: String) -> void:
    var resource = yield(load(path), "completed")
    if resource:
        print("Resource loaded: ", path)

# Signal callback function
func _on_button_pressed() -> void:
    print("Button was pressed!")

# Function with multiple return values using dictionary
func get_player_stats() -> Dictionary:
    return {
        "health": 100,
        "mana": 50,
        "position": Vector2(0, 0)
    }

# Function that uses signals
signal enemy_defeated(points)
func defeat_enemy(points: int) -> void:
    emit_signal("enemy_defeated", points)

# Function with type hints and assertions
func set_health(value: int) -> void:
    assert(value >= 0) # Ensure health is not negative
    var health = value

# Coroutine-style function
func _perform_sequence() -> void:
    print("Start sequence")
    yield(get_tree().create_timer(1.0), "timeout")
    print("After 1 second")
    yield(get_tree().create_timer(1.0), "timeout")
    print("Sequence complete")

# Test function to demonstrate various function calls
func _test_functions() -> void:
    # Test regular function
    var damage = calculate_damage(10.0, 1.5)
    print("Calculated damage: ", damage)
    
    # Test function with default parameters
    spawn_enemy()
    spawn_enemy(Vector2(100, 100), 200)
    
    # Test movement
    move_character(Vector2.RIGHT, 5.0)
    
    # Test static function
    var new_node = create_instance()
    add_child(new_node)
    
    # Test stats
    var stats = get_player_stats()
    print("Player stats: ", stats)
    
    # Test signal emission
    defeat_enemy(100)
    
    # Test health setting
    set_health(100)
    
    # Start sequence
    _perform_sequence()

# Connect signals in code
func _connect_signals() -> void:
    var button = Button.new()
    button.connect("pressed", self, "_on_button_pressed") 