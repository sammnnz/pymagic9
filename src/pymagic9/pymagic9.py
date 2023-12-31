"""
This module provides functions for analyzing call stacks such as `nameof`, `auto-implemented properties`, etc.
"""
import dis
import sys

from multipledispatch import dispatch, Dispatcher
from opcode import hasname, EXTENDED_ARG, HAVE_ARGUMENT
from types import CodeType, FunctionType
from typing import Any, Callable, Dict, Optional, Tuple, Union

# noinspection SpellCheckingInspection
__all__ = ["getframe", "isemptyfunction", "isfunctionincallchain", "nameof", "PropertyMeta"]


# noinspection SpellCheckingInspection
def _getframe(__depth=0):
    """
    Polyfill for the built-in sys._getframe function.

    Args:
        __depth (int, optional): The depth of the call stack to traverse. A value of 0 represents the current frame,
         1 represents the caller's frame, and so on.

    Returns:
        FrameType or None: The frame object at the specified depth in the call stack, or None if the depth is out of
        range.

    Raises:
        TypeError: If the depth argument is not an integer.
        ValueError: If call stack is not deep enough.

    This function provides a polyfill for the built-in `sys._getframe` function, which is used to access the call stack
    frames. It allows you to retrieve the frame object at a specific depth in the call stack.

    The depth argument specifies the number of frames to traverse. A value of 0 or less 0 represents the current frame,
    1 represents the caller's frame, and so on. If the depth is negative, it will traverse the frames in the opposite
    direction.

    If the specified depth is out of range (i.e., greater than the number of frames in the call stack), the function
    raises ValueEror.

    Examples:
        >>> def foo():
        ...     frame = _getframe(1)
        ...     print(frame.f_code.co_name)  # Output: bar
        >>> def bar():
        ...     foo()
        >>> bar()
        bar
    """

    if not isinstance(__depth, int):
        if sys.version_info >= (3, 5):
            raise TypeError('an integer is required (got type %s)' % type(__depth))
        elif sys.version_info < (3, ):  # pragma: no cover
            raise TypeError('an integer is required')

    try:
        raise TypeError
    except TypeError:
        tb = sys.exc_info()[2]

    if tb is None: return None  # noqa E702

    frame = tb.tb_frame.f_back
    del tb

    if __depth < 0: return frame  # noqa E702

    try:
        while __depth:  # while i and frame: to disable the exception
            frame = frame.f_back  # type: ignore #noqa
            __depth -= 1
    except AttributeError:
        raise ValueError('call stack is not deep enough')

    return frame


# noinspection PyUnresolvedReferences,SpellCheckingInspection,PyProtectedMember
getframe = sys._getframe if hasattr(sys, '_getframe') else _getframe


# noinspection SpellCheckingInspection
def isfunctionincallchain(o, __depth=-1):
    """
    Determines whether the given function object or code object is present in the call chain.

    Args:
        o (FunctionType or CodeType): The function object or code object to check.
        __depth (int, optional): The depth of the call chain to search. Default is -1, which means search the entire
         call chain.

    Returns:
        bool: True if the function or code object is found in the call chain, False otherwise.

    Raises:
        TypeError: If the input object is not a function or code object.

    This function checks if the given function object or code object is present in the call chain of the current
    execution. The call chain is the sequence of function calls that led to the current point of execution.

    Warning:
         Be careful when debugging in PyCharm - there may be incorrect behavior when a function that is being debugged
         (a function that has breakpoints) is passed as an argument.

    Examples:
        >>> def foo():
        ...     return isfunctionincallchain(foo)
        ...
        >>> def bar():
        ...     return isfunctionincallchain(foo)
        ...
        >>> def baz():
        ...     return foo()
        ...
        >>> print(foo())
        True
        >>> print(bar())
        False
        >>> print(baz())
        True
    """
    if not isinstance(o, (CodeType, FunctionType)):
        raise TypeError('\'o\' must be code or function')

    code = o if not hasattr(o, "__code__") else o.__code__  # type: ignore
    frame = getframe(1)
    while frame and __depth:
        if frame.f_code is code:
            return True

        __depth -= 1
        frame = frame.f_back

    return False


# noinspection SpellCheckingInspection,PyUnusedLocal
def nameof(o):
    """
    Returns the name of an object.

    Args:
        o (object): The object for which to retrieve the name.

    Returns:
        str: The name of the object or empty string.

    This function correctly determines the 'name' of an object, without being tied to the object itself.
    It can be used to retrieve the name of variables, functions, classes, modules, and more. An empty string will be
    returned if an explicit value or call is passed to the `nameof` function as an argument.

    Examples:
        >>> var1 = [1, 2]
        >>> var2 = var1
        >>> print(nameof(var1))
        var1
        >>> print(nameof(var2))
        var2
        >>> print(nameof(123))  # doctest:+SKIP
        empty string ("")
    """
    frame = getframe(1)
    f_code, f_lineno = frame.f_code, frame.f_lineno

    for line in dis.findlinestarts(f_code):
        if f_lineno == line[1]:
            ind = -3 if sys.version_info < (3,) else -2
            _, op, arg = next(_unpack_opargs(f_code.co_code[:frame.f_lasti][ind:]))

            if op not in hasname:
                return ''

            return f_code.co_names[arg]


# noinspection SpellCheckingInspection
def _unpack_opargs_py2(code):  # pragma: no cover
    """
    _unpack_opargs function for python2

    """
    extended_arg, i = 0, 0
    while i < len(code):
        op = ord(code[i])
        i += 1
        if op >= HAVE_ARGUMENT:
            arg = ord(code[i]) | ord(code[i + 1]) * 256 | extended_arg  # type: int | None
            extended_arg, i = 0, i + 2
            if op == EXTENDED_ARG:
                exec("extended_arg = arg * 65536L")  # py3 support
        else:
            arg = None

        yield i, op, arg


# noinspection SpellCheckingInspection
def _unpack_opargs_py3(code):
    """
    _unpack_opargs function for python3

    This function is a clone of the `dis._unpack_opargs` function from the Python 3.9.6 standard library's `dis`
    module.
    """
    extended_arg = 0
    for i in range(0, len(code), 2):
        op = code[i]
        if op >= HAVE_ARGUMENT:
            arg = code[i + 1] | extended_arg
            extended_arg = (arg << 8) if op == EXTENDED_ARG else 0
        else:
            arg = None

        yield i, op, arg


# noinspection SpellCheckingInspection
_unpack_opargs = _unpack_opargs_py2 if sys.version_info < (3,) else _unpack_opargs_py3
_unpack_opargs.__doc__ = """
Unpacks the opcodes and their arguments from the given bytecode. Works in Python 2.7 and Python 3.

Args:
    code (bytes): The bytecode to unpack.

Yields:
    tuple: A tuple containing the offset, opcode, and argument of each opcode.

It takes a bytecode object as input and yields a sequence of tuples containing the offset, opcode, and argument of each
opcode in the bytecode.
"""
del _unpack_opargs_py2, _unpack_opargs_py3


# noinspection SpellCheckingInspection
def isemptyfunction(func):
    """
    Checks if a function is empty or not.

    Args:
        func (function): The function to check.

    Returns:
        bool: True if the function is empty, False otherwise.

    Raises:
        TypeError: If the input object is not a function.

    This function determines whether the given function is empty or not. An empty function is defined here as a
    function that:
    - may contain operators pass, return;
    - may only return None;
    - may contain a documentation string (classic documentation string in triple quotes, in double/single quotes as
    `str` type, and also in `bytes` type) and comments;
    - may contain any unreachable code (see `odd_function` in Examples);
    - may contain statements to have no effect (see `odd_function` in Examples).
    If something else is present in the function, then it is considered not empty. It can be useful in scenarios where
    you need to check if a function has any implementation or if it is just a placeholder.

    The definition above may seem strange, but an empty function is defined this way for the sake of compatibility with
    the versions of Python supported by this project (since the interpreter behaves differently on different versions
    of Python, a simpler implementation of this function would return different values).

    Examples:
        >>> def empty_function():
        ...     pass
        ...
        >>> print(isemptyfunction(empty_function))
        True
        >>> def empty_function():
        ...     return
        ...
        >>> print(isemptyfunction(empty_function))
        True
        >>> def empty_function():
        ...     return None
        ...
        >>> print(isemptyfunction(empty_function))
        True
        >>> def empty_function():  # doctest:+SKIP
        ...     # only in Python3
        ...     ...
        ...
        >>> print(isemptyfunction(empty_function))
        True
        >>> def empty_function():
        ...     \""" docstring \"""
        ...
        >>> print(isemptyfunction(empty_function))
        True
        >>> def empty_function():
        ...     "doc"
        ...
        >>> print(isemptyfunction(empty_function))
        True
        >>> def empty_function():
        ...     b'Hello World!'
        ...     return
        >>> print(isemptyfunction(empty_function))
        True
        >>> def empty_function():
        ...     # comments
        ...     return
        ...
        >>> print(isemptyfunction(empty_function))
        True
        >>> def empty_function():
        ...     \""" docstring \"""
        ...     return
        ...
        >>> print(isemptyfunction(empty_function))
        True
        >>> empty_lambda = lambda x: None
        >>> print(isemptyfunction(empty_lambda))
        True
        >>> def non_empty_function():
        ...     print("Hello, world!")
        ...
        >>> print(isemptyfunction(non_empty_function))
        False
        >>> def non_empty_function():
        ...     return 0
        ...
        >>> print(isemptyfunction(non_empty_function))
        False
        >>> not_empty_lambda = lambda: 0
        >>> print(isemptyfunction(not_empty_lambda))
        False
        >>> # All odd_functions is empty!
        >>> def odd_function():  # statement (immutable) to have no effect
        ...     None
        ...     100
        ...     True
        ...     ()
        ...     "string"
        ...     b'd\x01'
        ...     return
        ...
        >>> print(isemptyfunction(odd_function))
        True
        >>> def odd_function():  # statement (mutable) to have no effect
        ...     []
        ...     return
        ...
        >>> print(isemptyfunction(odd_function))
        True
        >>> def odd_function(): \""" docstring \"""; return; None;  # oneline function and unreachable code
        >>> print(isemptyfunction(odd_function))
        True
        >>> def odd_function():  # unreachable code
        ...     return
        ...     a = 2
        ...
        >>> print(isemptyfunction(odd_function))
        True
    """
    if not isinstance(func, FunctionType):
        raise TypeError("'func' argument must be a function")

    code = func.__code__
    gen_opargs = _unpack_opargs(code.co_code)
    op, special_op, special_arg = 0, 0, 0
    for _, op, arg in gen_opargs:
        if op == 9:  # skip if NOP; py310
            continue

        if op == 1 and special_op:  # skip when POP_TOP next for special opcode
            special_op = 0
            continue

        if op >= HAVE_ARGUMENT:  # special opcode
            if op == EXTENDED_ARG:
                continue

            if not special_op:  # skip when first opcode have argument (special opcode)
                special_op, special_arg = op, arg
                continue

            return False  # two special opcodes in a row

        break

    if special_op != 100:  # first opcode must be LOAD_CONST
        return False

    if code.co_consts[special_arg] is not None:  # check for docstring
        return False

    return op == 83  # second opcode must be RETURN_VALUE


# noinspection PySuperArguments
class PropertyMeta(type):
    # noinspection SpellCheckingInspection,PyCompatibility
    """
    This metaclass allows you to create auto-implemented properties (like in C#, where you can declare properties
    without explicitly defining a getter and setter), for which you can use an ellipsis or empty functions to indicate
    that the Python itself would create the special accessor.

    Detailed working principle:

    1. Ordinary auto-implemented properties:

        .. code-block:: python

           property1 = property(..., ...)
           property1 = property(..., ..., ...)

        In this case, the following are created:

            - **dictionary** (in the closure of the metaclass initializer) for recording and retrieving the value;
            - **getter** that returns a value from the dictionary (if the value is not in the dictionary, then the
              ``AttributeError`` exception is thrown);
            - **setter** that writes a value to the dictionary if there is no value yet, or the value differs from that
              written in the dictionary;
            - **deleter** that deletes a value from the dictionary if it exists (if the value is not in the dictionary,
              then the ``AttributeError`` exception is thrown).

    2. Readonly auto-implemented properties:

        .. code-block:: python

           property1 = property(...)

        In this case, the following are created:

            - **dictionary** (in the closure of the metaclass initializer) for recording and retrieving the value;
            - **getter** that returns a value from the dictionary (if the value is not in the dictionary, then the
              ``AttributeError`` exception is thrown);
            - **setter** that can be called only once from the class initializer when creating an instance (when called
              again, the ``AttributeError`` exception is thrown);
            - **deleter** that deletes a value from the dictionary if it exists (if the value is not in the
              dictionary, then the ``AttributeError`` exception is thrown).

    3. Auto-implemented properties with custom getter:

        .. code-block:: python

           # getter is not empty function
           property1 = property(getter, ...)

        In this case, a custom getter remains. Otherwise, everything is the same as in the previous paragraphs.

    4. Auto-implemented properties with custom setter, deleter:

        .. code-block:: python

           # setter, deleter is not empty functions
           property1 = property(..., setter)
           property1 = property(..., ..., deleter)
           property1 = property(..., setter, deleter)

        In this case, the following are created:

            - **dictionary** (in the closure of the metaclass initializer) for recording and retrieving the value;
            - **getter** that returns a value from the dictionary (if the value is not in the dictionary, then the
              ``AttributeError`` exception is thrown);
            - **setter** that preserves the functionality of the initially defined user setter (that is, after the new
              value is written to the dictionary, the initially defined user setter is called).
            - **deleter** that preserves the functionality of the initially defined user deleter (that is, after
              deleting the value from the dictionary, the initially defined custom deleter is called).

    5. Properties that will not be processed by the PropertyMeta metaclass:

        .. code-block:: python

           # getter, setter, deleter is not empty functions
           property1 = property(getter)
           property1 = property(getter, setter)
           property1 = property(getter, setter, deleter)
           property1 = property(getter, setter, ...)

    Examples:
        1. Import the PropertyMeta metaclass and assign it as a metaclass for the desired class:

        .. code-block:: python

           from pymagic9 import PropertyMeta


           class Person(metaclass=PropertyMeta):
               pass

        2. Create properties in this class with empty accessors (using empty function or ellipsis) to indicate that
        this property will be auto-implemented:

        .. code-block:: python

           from pymagic9 import PropertyMeta


           class Person(metaclass=PropertyMeta):
               \"""class Person\"""
               def __init__(self, name):
                   self.name = name

               name = property(fget=...,)           # readonly property
               age = property(fget=..., fset=...,)  # ordinary property

        3. Now for an `ordinary` property we can get and put values into it at any time. But for a `readonly` property,
        you can put a value into it only once, at the time of creating an instance of the class:

        .. code-block:: python

           from pymagic9 import PropertyMeta


           class Person(metaclass=PropertyMeta):
               \"""class Person\"""
               def __init__(self, name):
                   self.name = name
                   # self.name = "Sam"  # raise AttributeError: 'property' is readonly (reassigning value)

               name = property(fget=...,)           # readonly property
               age = property(fget=..., fset=...,)  # ordinary property


           if __name__ == "__main__":
               person = Person("Tom")
               person.age = 24
               print(person.name + ',', person.age)  # Tom, 24
               # person.name = "Sam"  # raise AttributeError: 'property' is readonly

        4. To delete a property value, use the `del` operator:

        .. code-block:: python

           from pymagic9 import PropertyMeta


           class Person(metaclass=PropertyMeta):
               \"""class Person\"""
               def __init__(self, name):
                   self.name = name

               name = property(fget=...,)           # readonly property
               age = property(fget=..., fset=...,)  # ordinary property


           if __name__ == "__main__":
               person = Person("Tom")
               person.age = 24
               print(person.name + ',', person.age)  # Tom, 24
               del person.name
               # print(person.name)  # raise AttributeError: auto-implemented field does not exist or has already been
                                     # erased

        5. If the `getter` is specified by an empty accessor (using empty function or ellipsis), and the `setter` is
        not an empty function, then `setter` will also be called. This can be used as a callback when assigning a value
        to a property:

        .. code-block:: python

           from pymagic9 import nameof, PropertyMeta


           def NotifyPropertyChanged(propertyname, value):
               \"""Notify property changed\"""
               # Do something
               print(propertyname + ',', value)


           class Person(metaclass=PropertyMeta):
               \"""class Person\"""
               def __init__(self, name):
                   self.name = name

               name = property(fget=...,)           # readonly property
               age = property(fget=..., fset=...,)  # ordinary property

               @property
               def height(self):
                   \"""Person height in cm\"""
                   return

               @height.setter
               def height(self, value):
                   NotifyPropertyChanged(nameof(self.height), value)


           if __name__ == "__main__":
               person = Person("Tom")
               person.age = 24
               print(person.name + ',', person.age)  # Tom, 24
               person.height = 180  # height, 180

        6. Similar code for `Python 2.7` looks like this:

        .. code-block:: python

           from pymagic9 import nameof, PropertyMeta

           __metaclass__ = PropertyMeta


           def NotifyPropertyChanged(propertyname, value):
               \"""Notify property changed\"""
               # Do something
               print(propertyname + ', ' + str(value))


           class Person:
               \"""class Person\"""
               def __init__(self, name):
                   self.name = name

               name = property(fget=Ellipsis,)                # readonly property
               age = property(fget=Ellipsis, fset=Ellipsis,)  # ordinary property

               @property
               def height(self):
                   \"""Person height in cm\"""
                   return

               @height.setter
               def height(self, value):
                   NotifyPropertyChanged(nameof(self.height), value)


           if __name__ == "__main__":
               person = Person("Tom")
               person.age = 24
               print(person.name + ', ' + str(person.age))  # Tom, 24
               person.height = 180  # height, 180

    """

    # noinspection SpellCheckingInspection,PySuperArguments
    def __init__(cls, name, bases, attrs):
        super(PropertyMeta, cls).__init__(name, bases, attrs)
        del_ns = {}  # type: Dict[str, Dispatcher]
        set_ns = {}  # type: Dict[str, Dispatcher]

        @dispatch(dict, namespace=del_ns)  # noqa: F811
        def _deleter(fi):  # noqa: F811
            def _wrapper(self):
                try:
                    del fi[(self,)]
                except KeyError:
                    raise AttributeError(
                        "auto-implemented field does not exist or has already been erased"
                    )

            return _wrapper

        # deleter for overriding an existing deleter
        # noinspection SpellCheckingInspection
        @dispatch(type, FunctionType, dict, namespace=del_ns)  # type: ignore # noqa: F811
        def _deleter(_cls, _fdel, fi):
            def _wrapper(self, *args):
                try:
                    del fi[(self,)]
                except KeyError:
                    pass
                finally:
                    return _fdel(self, *args)

            return _wrapper

        def _getter(fi):
            def _wrapper(self):
                try:
                    return fi[(self,)]
                except KeyError:
                    raise AttributeError(
                        "auto-implemented field does not exist or has already been erased"
                    )

            return _wrapper

        @dispatch(dict, namespace=set_ns)  # noqa: F811
        def _setter(fi):  # noqa: F811
            def _wrapper(self, value):
                try:
                    fi[(self,)]
                except KeyError:
                    fi[(self,)] = value
                else:
                    if fi[(self,)] != value:
                        fi[(self,)] = value

            return _wrapper

        # setter for readonly properties
        @dispatch(dict, (CodeType, type(None)), CodeType, namespace=set_ns)  # type: ignore # noqa: F811
        def _setter(fi, init_code, call_code):  # noqa: F811
            def _wrapper(self, value):
                try:
                    fi[(self,)]
                except KeyError:
                    pass
                else:
                    raise AttributeError("'property' is readonly")

                frame = getframe(1)
                # Cautious during debugging: if the stop point falls into
                # the __init__ / __call__ function, then its duplicate may
                # be called and, as a result, the code objects will vary.
                if init_code is frame.f_code and call_code is frame.f_back.f_code:
                    fi[(self,)] = value

                    return

                raise AttributeError("'property' is readonly")

            return _wrapper

        # setter for overriding an existing setter
        # noinspection SpellCheckingInspection
        @dispatch(FunctionType, dict, namespace=set_ns)  # type: ignore # noqa: F811
        def _setter(_fset, fi):  # noqa: F811
            def _wrapper(self, value):
                try:
                    fi[(self,)]
                except KeyError:
                    fi[(self,)] = value
                else:
                    if fi[(self,)] != value:
                        fi[(self,)] = value

                return _fset(self, value)

            return _wrapper

        for key, obj in attrs.items():
            if not isinstance(obj, property):
                continue

            fget = obj.fget  # type: Union[Optional[Callable[[Any], Any]], ellipsis]  # noqa: F821
            fset = obj.fset  # type: Union[Optional[Callable[[Any, Any], None]], ellipsis]  # noqa: F821
            fdel = obj.fdel  # type: Union[Optional[Callable[[Any], None]], ellipsis]  # noqa: F821
            is_accessor_gen = False
            fields = {}  # type: Dict[Tuple[type], Any]

            if _is_autoimplemented_accessor(fget):
                fget = _getter(fields)
                is_accessor_gen = True

                if fdel is None:
                    fdel = Ellipsis

            if _is_autoimplemented_accessor(fset):
                fset = _setter(fields)
                is_accessor_gen = True

                if fdel is None:
                    fdel = Ellipsis
            elif fset is None and is_accessor_gen:  # for readonly properties (initialize in constructor of class)
                fset = _setter(
                    fields,
                    getattr(getattr(cls, "__init__", None), '__code__'),
                    PropertyMeta.__call__.__code__
                )
            elif is_accessor_gen:
                fset = _setter(fset, fields)

            if _is_autoimplemented_accessor(fdel):
                fdel = _deleter(fields)
                is_accessor_gen = True
            elif fdel is not None and is_accessor_gen:
                fdel = _deleter(cls, fdel, fields)

            if is_accessor_gen:
                setattr(cls, key, property(fget, fset, fdel, obj.doc if hasattr(obj, 'doc') else None))  # type: ignore

            del fdel, fget, fset, fields

        del del_ns, set_ns
        del _deleter, _getter, _setter

    # __call__ implement here for readonly properties
    # noinspection PyTypeChecker
    def __call__(cls, *args, **kwargs):
        instance = object.__new__(cls)
        instance.__init__(*args, **kwargs)
        return instance


def _is_autoimplemented_accessor(accessor):
    """
    Accessor is auto-implemented if it is an ellipsis or an empty function.

    """
    if accessor is None:
        return False
    elif accessor is Ellipsis:
        return True

    return isemptyfunction(accessor)
