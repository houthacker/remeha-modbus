"""itertools method helpers.

Copyright (c) 2012 Erik Rose

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""

from collections.abc import Mapping
from itertools import groupby
from operator import itemgetter
from typing import Generic, Self, TypeVar


def consecutive_groups(iterable, ordering=lambda x: x):
    """Yield groups of consecutive items using :func:`itertools.groupby`.

    *Attribution:*
    This method is copied from the [more-itertools](https://more-itertools.readthedocs.io/en/stable/_modules/more_itertools/more.html#consecutive_groups)
    library to prevent a new dependency just for a single method.

    The *ordering* function determines whether two items are adjacent by
    returning their position.

    By default, the ordering function is the identity function. This is
    suitable for finding runs of numbers:

        >>> iterable = [1, 10, 11, 12, 20, 30, 31, 32, 33, 40]
        >>> for group in consecutive_groups(iterable):
        ...     print(list(group))
        [1]
        [10, 11, 12]
        [20]
        [30, 31, 32, 33]
        [40]

    For finding runs of adjacent letters, try using the :meth:`index` method
    of a string of letters:

        >>> from string import ascii_lowercase
        >>> iterable = 'abcdfgilmnop'
        >>> ordering = ascii_lowercase.index
        >>> for group in consecutive_groups(iterable, ordering):
        ...     print(list(group))
        ['a', 'b', 'c', 'd']
        ['f', 'g']
        ['i']
        ['l', 'm', 'n', 'o', 'p']

    Each group of consecutive items is an iterator that shares it source with
    *iterable*. When an an output group is advanced, the previous group is
    no longer available unless its elements are copied (e.g., into a ``list``).

        >>> iterable = [1, 2, 11, 12, 21, 22]
        >>> saved_groups = []
        >>> for group in consecutive_groups(iterable):
        ...     saved_groups.append(list(group))  # Copy group elements
        >>> saved_groups
        [[1, 2], [11, 12], [21, 22]]

    """
    for _, g in groupby(enumerate(iterable), key=lambda x: x[0] - ordering(x[1])):
        yield map(itemgetter(1), g)


K = TypeVar("K")
V = TypeVar("V")


class UnmodifiableDict(Mapping, Generic[K, V]):
    """A `Mapping` implementation ."""

    def __init__(self, data: dict[K, V]):
        """Create a new read-only mapping using `data` as its backing dictionary."""

        self._store: dict[K, V] = data

    @classmethod
    def snapshot(cls, data: dict[K, V]) -> Self:
        """Take a snapshot of `data` and use that to create a new unmodifiable mapping.`.

        Args:
            data (dict[K, V]): The source dictionary.

        Returns:
            The new mapping.

        """

        return UnmodifiableDict(data=dict(data))

    @classmethod
    def create(cls, data: dict[K, V]) -> Self:
        """Create a read-only view of `data`.

        Note: since `data` is referenced and not copied, changing it from another point of view
        change the backing data of the returned dict.

        Args:
            data (dict[K, V]): The dictionary to create a view from.

        Returns:
            The new mapping.

        """

        return UnmodifiableDict(data=data)

    def __getitem__(self, key: K) -> V:
        """Return the value of the mapping with key `key`.

        Args:
            key (K): The key of the value to retrieve.

        Raises:
            KeyError: if the key does not exist in this mapping.

        """

        return self._data[key]

    def __iter__(self):
        """Return an iterator over the keys of this dict."""

        yield from self._store

    def __len__(self) -> int:
        """Return the amount of key/value pairs in this dict."""

        return len(self._store)
