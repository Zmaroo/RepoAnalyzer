"""Test file for syntax pattern detection."""

# Function with decorator
@property
def decorated_function():
    """Function with a decorator."""
    return 42

# Class with multiple decorators
@dataclass
@total_ordering
class DecoratedClass:
    """Class with decorators."""
    value: int
    name: str
    
    def __init__(self, value: int, name: str):
        self.value = value
        self.name = name
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(data['value'], data['name'])
    
    @staticmethod
    def helper():
        return "Helper method"

# Function with type hints
def typed_function(x: int, y: str) -> bool:
    return len(y) == x

# Class with inheritance
class BaseClass:
    def base_method(self):
        pass

class DerivedClass(BaseClass):
    def derived_method(self):
        super().base_method()

# Enum definition
class Colors(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3

# Interface/Protocol
class DataProcessor(Protocol):
    def process(self, data: Any) -> Any:
        ...

# Constructor
class ConstructorTest:
    def __init__(self, arg1, arg2):
        self.arg1 = arg1
        self.arg2 = arg2

# Method with different decorators
class MethodTest:
    @abstractmethod
    def abstract_method(self):
        pass
    
    @property
    def prop(self):
        return self._prop
    
    @prop.setter
    def prop(self, value):
        self._prop = value 