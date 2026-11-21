"""Fixed-size ring buffer of recent signal readings."""


class SignalHistoryBuffer:
    def __init__(self, maxlen: int = 100):
        self._buf: list[float | None] = [None] * maxlen
        self._max = maxlen
        self._pos = 0
        self._count = 0

    def push(self, value: float):
        self._buf[self._pos] = value
        self._pos = (self._pos + 1) % self._max
        self._count = min(self._count + 1, self._max)

    def get_all(self) -> list[float | None]:
        if self._count < self._max:
            return self._buf[: self._count]
        return self._buf[self._pos :] + self._buf[: self._pos]

    def clear(self):
        self._buf = [None] * self._max
        self._pos = 0
        self._count = 0
