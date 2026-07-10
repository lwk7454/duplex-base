"""Minimal `expect` DSL for BDD-style tests (no external deps).

Usage:
    expect(value).to_equal(other)
    expect(value).to_be_truthy()
    expect(callable).to_raise(ValueError)
"""

from __future__ import annotations

from typing import Any, Callable


class Expectation:
    def __init__(self, actual: Any):
        self._actual = actual

    def to_equal(self, expected: Any) -> None:
        assert self._actual == expected, f"expected {self._actual!r} to equal {expected!r}"

    def to_not_equal(self, other: Any) -> None:
        assert self._actual != other, f"expected {self._actual!r} to differ from {other!r}"

    def to_be_truthy(self) -> None:
        assert bool(self._actual), f"expected {self._actual!r} to be truthy"

    def to_be_falsy(self) -> None:
        assert not bool(self._actual), f"expected {self._actual!r} to be falsy"

    def to_be_none(self) -> None:
        assert self._actual is None, f"expected None, got {self._actual!r}"

    def to_not_be_none(self) -> None:
        assert self._actual is not None, f"expected not-None"

    def to_contain(self, item: Any) -> None:
        assert item in self._actual, f"expected {item!r} in {self._actual!r}"

    def to_have_length(self, n: int) -> None:
        assert len(self._actual) == n, f"expected length {n}, got {len(self._actual)}"

    def to_be_instance_of(self, cls: type) -> None:
        assert isinstance(self._actual, cls), f"expected {type(self._actual)} to be {cls}"


def expect(actual: Any) -> Expectation:
    return Expectation(actual)


def to_raise(expected_exc: type[BaseException]) -> Callable:
    """Decorator/awaitable-free context: use as `expect(fn).to_raise(X)` via helper below."""

    def _check(fn: Callable, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except expected_exc:
            return
        raise AssertionError(f"expected {expected_exc.__name__} to be raised")

    return _check  # noqa: this is wrapped by raises() below


import contextlib


@contextlib.contextmanager
def raises(expected_exc: type[BaseException]):
    try:
        yield
    except expected_exc:
        return
    raise AssertionError(f"expected {expected_exc.__name__} to be raised")
