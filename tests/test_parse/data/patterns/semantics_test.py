from __future__ import annotations
from typing import TypeVar, Generic, Protocol, runtime_checkable
from dataclasses import dataclass
from abc import ABC, abstractmethod
import asyncio
from contextlib import contextmanager

# Type variable for generics
T = TypeVar('T')

# Protocol definition
@runtime_checkable
class Printable(Protocol):
    def __str__(self) -> str: ...

# Abstract base class
class Animal(ABC):
    @abstractmethod
    def speak(self) -> str:
        pass

# Dataclass with type hints
@dataclass
class Point:
    x: float
    y: float
    
    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

# Generic class
class Container(Generic[T]):
    def __init__(self, item: T):
        self._item = item
    
    def get(self) -> T:
        return self._item

# Context manager
@contextmanager
def managed_resource():
    print("Resource acquired")
    try:
        yield "resource"
    finally:
        print("Resource released")

# Decorator pattern
def log_calls(func):
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        result = func(*args, **kwargs)
        print(f"Finished {func.__name__}")
        return result
    return wrapper

# Property usage
class Temperature:
    def __init__(self, celsius: float):
        self._celsius = celsius
    
    @property
    def celsius(self) -> float:
        return self._celsius
    
    @celsius.setter
    def celsius(self, value: float):
        self._celsius = value
    
    @property
    def fahrenheit(self) -> float:
        return (self._celsius * 9/5) + 32

# Async/await pattern
async def fetch_data():
    await asyncio.sleep(1)
    return "data"

# Generator pattern
def number_generator():
    yield 1
    yield from [2, 3, 4]
    yield 5

# Metaclass usage
class SingletonMeta(type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Singleton(metaclass=SingletonMeta):
    pass

# Multiple inheritance with mixin
class PrintMixin:
    def print_details(self):
        print(f"Instance of {self.__class__.__name__}")

class Named:
    def __init__(self, name: str):
        self.name = name

class Person(Named, PrintMixin):
    def __init__(self, name: str, age: int):
        super().__init__(name)
        self.age = age

# Descriptor protocol
class ValidatedString:
    def __init__(self, minlen: int = 0):
        self.minlen = minlen
    
    def __get__(self, obj, objtype=None):
        return obj.__dict__.get(self.name, '')
    
    def __set__(self, obj, value):
        if len(value) < self.minlen:
            raise ValueError(f"String must be at least {self.minlen} characters")
        obj.__dict__[self.name] = value
    
    def __set_name__(self, owner, name):
        self.name = name

# Example usage
class User:
    name = ValidatedString(minlen=3)
    
    def __init__(self, name: str):
        self.name = name

if __name__ == "__main__":
    # Context manager usage
    with managed_resource() as r:
        print(f"Using {r}")
    
    # Decorator usage
    @log_calls
    def example_function():
        print("Function body")
    
    example_function()
    
    # Property usage
    temp = Temperature(25)
    print(f"{temp.celsius}°C is {temp.fahrenheit}°F")
    
    # Generator usage
    for num in number_generator():
        print(num)
    
    # Multiple inheritance usage
    person = Person("Alice", 30)
    person.print_details()
    
    # Descriptor usage
    user = User("Bob")  # This will work
    try:
        user.name = "A"  # This will raise ValueError
    except ValueError as e:
        print(f"Validation error: {e}") 