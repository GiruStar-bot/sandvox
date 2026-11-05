# Godot's Array.sort_custom: SortArray of core/templates/sort_array.h (introsort, threshold 16, median of 3, a heap sort at depth 0,
# the final insertion sort), so rows that tie under the comparator come out in Godot's order (LC_HH_PORT_PLAN §4, rows L0-sort, L1-sort)
# Why not sorted(): it is stable, and Godot's order within ties is not; LC.quartile_cuts sums weights in the sorted order
THRESHOLD = 16


def sort_custom(a, less):
    n = len(a)
    if n:
        _introsort(a, 0, n, less, _bitlog(n) * 2)
        _final_insertion_sort(a, 0, n, less)
    return a


def _bitlog(n):
    k = 0
    while n != 1:
        n >>= 1
        k += 1
    return k


def _median_of_3(a, b, c, less):
    if less(a, b):
        if less(b, c):
            return b
        if less(a, c):
            return c
        return a
    if less(a, c):
        return a
    if less(b, c):
        return c
    return b


def _push_heap(arr, first, hole, top, value, less):
    parent = (hole - 1) // 2
    while hole > top and less(arr[first + parent], value):
        arr[first + hole] = arr[first + parent]
        hole = parent
        parent = (hole - 1) // 2
    arr[first + hole] = value


def _adjust_heap(arr, first, hole, length, value, less):
    top = hole
    second = 2 * hole + 2
    while second < length:
        if less(arr[first + second], arr[first + second - 1]):
            second -= 1
        arr[first + hole] = arr[first + second]
        hole = second
        second = 2 * (second + 1)
    if second == length:
        arr[first + hole] = arr[first + second - 1]
        hole = second - 1
    _push_heap(arr, first, hole, top, value, less)


def _pop_heap_to(arr, first, last, result, value, less):
    arr[result] = arr[first]
    _adjust_heap(arr, first, 0, last - first, value, less)


def _make_heap(arr, first, last, less):
    # Why not SortArray's `last - first < 2` return: the only caller (introsort's depth limit) has last - first > 16 (§7.1)
    length = last - first
    parent = (length - 2) // 2
    while True:
        _adjust_heap(arr, first, parent, length, arr[first + parent], less)
        if parent == 0:
            return
        parent -= 1


def _sort_heap(arr, first, last, less):
    while last - first > 1:
        _pop_heap_to(arr, first, last - 1, last - 1, arr[last - 1], less)
        last -= 1


def _partial_sort(arr, first, last, middle, less):
    # Why not SortArray's loop over [middle, last): the only caller passes middle == last, so that range is empty (§7.1)
    _make_heap(arr, first, middle, less)
    _sort_heap(arr, first, middle, less)


def _partitioner(arr, first, last, pivot, less):
    while True:
        while less(arr[first], pivot):
            first += 1
        last -= 1
        while less(pivot, arr[last]):
            last -= 1
        if not first < last:
            return first
        arr[first], arr[last] = arr[last], arr[first]
        first += 1


def _introsort(arr, first, last, less, depth):
    while last - first > THRESHOLD:
        if depth == 0:
            _partial_sort(arr, first, last, last, less)
            return
        depth -= 1
        cut = _partitioner(arr, first, last, _median_of_3(arr[first], arr[first + (last - first) // 2], arr[last - 1], less), less)
        _introsort(arr, cut, last, less, depth)
        last = cut


def _unguarded_linear_insert(arr, last, value, less):
    nxt = last - 1
    while less(value, arr[nxt]):
        arr[last] = arr[nxt]
        last = nxt
        nxt -= 1
    arr[last] = value


def _linear_insert(arr, first, last, less):
    val = arr[last]
    if less(val, arr[first]):
        for i in range(last, first, -1):
            arr[i] = arr[i - 1]
        arr[first] = val
    else:
        _unguarded_linear_insert(arr, last, val, less)


def _insertion_sort(arr, first, last, less):
    # Why not SortArray's `first == last` return: sort_custom sorts only n > 0, so every call has last > first (§7.1)
    for i in range(first + 1, last):
        _linear_insert(arr, first, i, less)


def _final_insertion_sort(arr, first, last, less):
    if last - first > THRESHOLD:
        _insertion_sort(arr, first, first + THRESHOLD, less)
        for i in range(first + THRESHOLD, last):
            _unguarded_linear_insert(arr, i, arr[i], less)
    else:
        _insertion_sort(arr, first, last, less)
