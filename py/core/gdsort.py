# Godot's Array.sort() and sort_custom(): core/templates/sort_array.h's introsort (median of three, a heap sort past the depth
# limit, a final insertion sort over runs of 16), with Variant's OP_LESS for sort(). Why not Python's sorted: Godot's sort is not
# stable, so where a comparator has ties the order depends on its algorithm, and a port must give the same order to keep the digest
# (row G-sort, START_PORT_PLAN §2)

THRESHOLD = 16


_RANK = {bool: 1, int: 2, float: 3, str: 4, list: 28}


def _array_less(a, b):
    for x, y in zip(a, b):
        if _variant_less(x, y):
            return True
        if _variant_less(y, x):
            return False
    return len(a) < len(b)


def _variant_less(a, b):
    # Variant::operator<, which Array's own < uses on its elements: two types are ordered by their type (bool, int, float,
    # String, ..., Array) whatever their values, so 3.0 comes after 12 inside an array
    ta = _RANK[type(a)]
    tb = _RANK[type(b)]
    if ta != tb:
        return ta < tb
    if ta == 28:
        return _array_less(a, b)
    return a < b


def gd_less(a, b):
    # Variant OP_LESS as Array.sort() evaluates it: numbers with numbers (an int with a float by value), strings by code point,
    # arrays by Array's own <; any other pair is not ordered (false). Row G-sort found the two rules by their outputs
    na = type(a) in (int, float)
    nb = type(b) in (int, float)
    if na and nb:
        return a < b
    if type(a) is str and type(b) is str:
        return a < b
    if type(a) is list and type(b) is list:
        return _array_less(a, b)
    return False


class _Sorter:
    __slots__ = ("c",)

    def __init__(self, compare):
        self.c = compare

    def median_of_3(self, a, b, c):
        cmp = self.c
        if cmp(a, b):
            if cmp(b, c):
                return b
            if cmp(a, c):
                return c
            return a
        if cmp(a, c):
            return a
        if cmp(b, c):
            return c
        return b

    @staticmethod
    def bitlog(n):
        k = 0
        while n != 1:
            n >>= 1
            k += 1
        return k

    def push_heap(self, first, hole, top, value, arr):
        cmp = self.c
        parent = (hole - 1) // 2
        while hole > top and cmp(arr[first + parent], value):
            arr[first + hole] = arr[first + parent]
            hole = parent
            parent = (hole - 1) // 2
        arr[first + hole] = value

    def adjust_heap(self, first, hole, length, value, arr):
        cmp = self.c
        top = hole
        second = 2 * hole + 2
        while second < length:
            if cmp(arr[first + second], arr[first + (second - 1)]):
                second -= 1
            arr[first + hole] = arr[first + second]
            hole = second
            second = 2 * (second + 1)
        if second == length:
            arr[first + hole] = arr[first + (second - 1)]
            hole = second - 1
        self.push_heap(first, hole, top, value, arr)

    def pop_heap_to(self, first, last, result, value, arr):
        arr[result] = arr[first]
        self.adjust_heap(first, 0, last - first, value, arr)

    def pop_heap(self, first, last, arr):
        self.pop_heap_to(first, last - 1, last - 1, arr[last - 1], arr)

    def sort_heap(self, first, last, arr):
        while last - first > 1:
            self.pop_heap(first, last, arr)
            last -= 1

    def make_heap(self, first, last, arr):
        if last - first < 2:
            return
        length = last - first
        parent = (length - 2) // 2
        while True:
            self.adjust_heap(first, parent, length, arr[first + parent], arr)
            if parent == 0:
                return
            parent -= 1

    def partial_sort(self, first, last, middle, arr):
        cmp = self.c
        self.make_heap(first, middle, arr)
        for i in range(middle, last):
            if cmp(arr[i], arr[first]):
                self.pop_heap_to(first, middle, i, arr[i], arr)
        self.sort_heap(first, middle, arr)

    def partitioner(self, first, last, pivot, arr):
        cmp = self.c
        while True:
            while cmp(arr[first], pivot):
                first += 1
            last -= 1
            while cmp(pivot, arr[last]):
                last -= 1
            if not first < last:
                return first
            arr[first], arr[last] = arr[last], arr[first]
            first += 1

    def introsort(self, first, last, arr, depth):
        while last - first > THRESHOLD:
            if depth == 0:
                self.partial_sort(first, last, last, arr)
                return
            depth -= 1
            cut = self.partitioner(first, last, self.median_of_3(arr[first], arr[first + (last - first) // 2], arr[last - 1]),
                                   arr)
            self.introsort(cut, last, arr, depth)
            last = cut

    def unguarded_linear_insert(self, last, value, arr):
        cmp = self.c
        nxt = last - 1
        while cmp(value, arr[nxt]):
            arr[last] = arr[nxt]
            last = nxt
            nxt -= 1
        arr[last] = value

    def linear_insert(self, first, last, arr):
        val = arr[last]
        if self.c(val, arr[first]):
            for i in range(last, first, -1):
                arr[i] = arr[i - 1]
            arr[first] = val
        else:
            self.unguarded_linear_insert(last, val, arr)

    def insertion_sort(self, first, last, arr):
        if first == last:
            return
        for i in range(first + 1, last):
            self.linear_insert(first, i, arr)

    def unguarded_insertion_sort(self, first, last, arr):
        for i in range(first, last):
            self.unguarded_linear_insert(i, arr[i], arr)

    def final_insertion_sort(self, first, last, arr):
        if last - first > THRESHOLD:
            self.insertion_sort(first, first + THRESHOLD, arr)
            self.unguarded_insertion_sort(first + THRESHOLD, last, arr)
        else:
            self.insertion_sort(first, last, arr)

    def sort(self, arr):
        n = len(arr)
        if n != 0:
            self.introsort(0, n, arr, self.bitlog(n) * 2)
            self.final_insertion_sort(0, n, arr)


def sort(arr):
    # Array.sort() in place
    _Sorter(gd_less).sort(arr)
    return arr


def sort_custom(arr, less):
    # Array.sort_custom(less) in place
    _Sorter(less).sort(arr)
    return arr
