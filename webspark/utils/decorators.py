class cached_property:
    """A property decorator that caches the return value of a method.

    The method's result is computed once and then cached as a property of the instance.
    Subsequent accesses return the cached value without calling the method again.

    Example:
        class MyClass:
            @cached_property
            def expensive_computation(self):
                # This computation runs only once per instance
                return sum(range(1000000))

        obj = MyClass()
        result = obj.expensive_computation  # Computed and cached
        result2 = obj.expensive_computation   # Returns cached value

    Attributes:
        func: The decorated function/method.
        __name__: The name of the property.
        __module__: The module where the property is defined.
        __doc__: The docstring of the property.
    """

    def __init__(self, func, name=None, doc=None):
        """Initialize the cached_property decorator.

        Args:
            func: The function to be decorated.
            name: Optional name for the property. If not provided, uses function's name.
            doc: Optional docstring. If not provided, uses function's docstring.
        """
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, _=None):
        """Get the cached property value.

        Args:
            obj: The instance object.
            _: The class (unused).

        Returns:
            The cached value if it exists, otherwise computes and caches it.
        """
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, Ellipsis)
        if value is Ellipsis:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value
