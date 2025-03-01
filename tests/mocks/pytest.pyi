from typing import Any, Callable, TypeVar

T = TypeVar('T')
S = TypeVar('S')
F = TypeVar('F')

# Define FixtureFunction with two type parameters to match pytest 8.3.4
FixtureFunction = Callable[..., Any]  # Simple definition that works for all contexts

def fixture(*args, **kwargs) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ... 