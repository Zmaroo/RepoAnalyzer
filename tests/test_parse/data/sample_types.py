#!/usr/bin/env python3

# Regular function
def regular_function():
    return "Hello"

# Function with parameters and type hints
def typed_function(name: str, age: int) -> str:
    return f"Hello {name}, you are {age} years old"

# Async function
async def async_function():
    return "async result"

# Class with methods
class TestClass:
    def __init__(self):
        self.value = 42

    def instance_method(self):
        return self.value

    @classmethod
    def class_method(cls):
        return "class method"

    @staticmethod
    def static_method():
        return "static method"

    @property
    def property_method(self):
        return self.value

# Lambda function
lambda_func = lambda x: x * 2

# Nested function
def outer_function(x):
    def inner_function(y):
        return x + y
    return inner_function

# Generator function
def generator_function():
    yield 1
    yield 2

# Decorator function
def decorator(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

# Function with default arguments
def default_args(x, y=10, z="default"):
    return x, y, z

# Function with *args and **kwargs
def variadic_function(*args, **kwargs):
    return args, kwargs

# Async generator
async def async_generator():
    for i in range(3):
        yield i

# Abstract method in abstract class
from abc import ABC, abstractmethod


class AbstractClass(ABC):
    @abstractmethod
    def abstract_method(self):
        pass 