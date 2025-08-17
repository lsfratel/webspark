from webspark.utils.decorators import cached_property


def test_cached_property_caches_value():
    """Test that cached_property caches the result of a method."""

    class MyClass:
        def __init__(self):
            self.computation_count = 0

        @cached_property
        def expensive_computation(self):
            self.computation_count += 1
            return 42

    obj = MyClass()
    assert obj.computation_count == 0

    # First access
    result1 = obj.expensive_computation
    assert result1 == 42
    assert obj.computation_count == 1

    # Second access
    result2 = obj.expensive_computation
    assert result2 == 42
    assert obj.computation_count == 1  # Should not have increased


def test_cached_property_is_instance_specific():
    """Test that cached_property is specific to each instance."""

    class MyClass:
        call_count = 0

        @cached_property
        def my_property(self):
            MyClass.call_count += 1
            return MyClass.call_count

    obj1 = MyClass()
    obj2 = MyClass()

    assert obj1.my_property == 1
    assert obj1.my_property == 1  # Cached
    assert obj2.my_property == 2
    assert obj2.my_property == 2  # Cached
    assert MyClass.call_count == 2


def test_cached_property_docstring():
    """Test that cached_property preserves the docstring."""

    class MyClass:
        @cached_property
        def my_property(self):
            """This is a docstring."""
            return "value"

    assert MyClass.my_property.__doc__ == "This is a docstring."


def test_cached_property_on_class():
    class MyClass:
        @cached_property
        def my_property(self):
            return "value"

    assert isinstance(MyClass.my_property, cached_property)
