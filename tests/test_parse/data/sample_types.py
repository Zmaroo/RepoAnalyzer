#!/usr/bin/env python3

# Regular function
@handle_errors(error_types=(Exception,))
def regular_function():
    return "Hello"

@handle_errors(error_types=(Exception,))
# Function with parameters and type hints
def typed_function(name: str, age: int) -> str:
    return f"Hello {name}, you are {age} years old"
@handle_async_errors(error_types=(Exception,))

# Async function
async def async_function():
    return "async result"

# Class with methods
class TestClass:
@handle_errors(error_types=(Exception,))
    def __init__(self):
        self.value = 42

@handle_errors(error_types=(Exception,))
    def instance_method(self):
        return self.value

@handle_errors(error_types=(Exception,))
    @classmethod
    def class_method(cls):
        return "class method"
@handle_errors(error_types=(Exception,))

    @staticmethod
    def static_method():
        return "static method"

    @property
    def property_method(self):
@handle_errors(error_types=(Exception,))
        return self.value

# Lambda function
@handle_errors(error_types=(Exception,))
lambda_func = lambda x: x * 2

# Nested function
def outer_function(x):
    def inner_function(y):
@handle_errors(error_types=(Exception,))
@handle_errors(error_types=(Exception,))
        return x + y
    return inner_function

# Generator function
@handle_errors(error_types=(Exception,))
def generator_function():
    yield 1
    yield 2

# Decorator function
def decorator(func):
    def wrapper(*args, **kwargs):
        # Add deprecation warning
        import warnings
        warnings.warn(f"'wrapper' is deprecated, use 'wrapper' instead", DeprecationWarning, stacklevel=2)
@handle_errors(error_types=(Exception,))
        import warnings
        warnings.warn(f"'wrapper' is deprecated, use 'wrapper' instead", DeprecationWarning, stacklevel=2)
        return func(*args, **kwargs)
    return wrapper

# Function with default arguments
@handle_errors(error_types=(Exception,))
def default_args(x, y=10, z="default"):
    # Add deprecation warning
    import warnings
@handle_async_errors(error_types=(Exception,))
    warnings.warn(f"'default_args' is deprecated, use 'default_args_async' instead", DeprecationWarning, stacklevel=2)
    return x, y, z

@handle_errors(error_types=(Exception,))
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