import bisect


class Timeline:
    """Create timeline given start time and duration.

    Usage examples:
    >>> timeline = Timeline(start_time=-1, duration=10)  # start_time < 0 is allowed
    >>> print(timeline.start, timeline.end, timeline.duration)
    -1 9 10
    >>> timeline.now()
    -1
    >>> timeline.play(3.0)  # x2 speed
    >>> timeline.render(0.5)  # walltime, playback 0.5 * 3.0 for timeline actually
    >>> timeline.now()
    0.5
    >>> timeline.pause()  # set playback speed to 0
    >>> timeline.render(0.5)
    >>> timeline.now()
    0.5
    >>> timeline.stop()
    >>> timeline.now()
    -1
    >>> timeline.end = 5
    >>> print(timeline.start, timeline.end, timeline.duration)
    -1 5 6
    >>> timeline.duration = 12
    >>> print(timeline.start, timeline.end, timeline.duration)
    -1 11 12
    >>> timeline.start = 2
    >>> print(timeline.start, timeline.end, timeline.duration)
    2 14 12

    Errors that may raise:
    >>> timeline = Timeline(duration=-0.1)
    Traceback (most recent call last):
      ...
    ValueError: [Timeline] Duration must be non-negative!
    >>> timeline = Timeline(start_time=3, duration=10)
    >>> timeline.end = 2
    Traceback (most recent call last):
      ...
    ValueError: [Timeline] End time must be equal to or greater than start time!
    """
    __slots__ = ('_start_time', '_end_time', '_duration', '_head', '_direction', '_loop_enabled')

    def __init__(self, start_time=0.0, duration=0.0, loop_enabled=True):

        # Valid duration
        self.validDuration(duration)

        # Start time, duration and end time
        self._start_time = start_time
        self._duration = duration
        self._end_time = self._start_time + self._duration

        # Current timestamp (head)
        self._head = self.start

        # Direction (forward/backward) * playback speed
        self._direction = 0.0

        # Enable/Disable looped playback
        self._loop_enabled = loop_enabled

    @property
    def start(self):
        return self._start_time

    @start.setter
    def start(self, value):
        self._start_time = value
        self._end_time = self._start_time + self._duration

    @property
    def end(self):
        return self._end_time

    @end.setter
    def end(self, value):
        # Validator
        self.validEndTime(value)
        # Set value
        self._end_time = value
        self._duration = self._end_time - self._start_time

    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        # Validator
        self.validDuration(value)
        # Set value
        self._duration = value
        self._end_time = self._start_time + self._duration

    def validEndTime(self, value):
        if value <= self._start_time:
            raise ValueError(f'[{self.__class__.__name__}] End time must be equal to or greater than start time!')

    def validDuration(self, value):
        if value < 0:
            raise ValueError(f'[{self.__class__.__name__}] Duration must be non-negative!')

    def loop(self):
        # Toggle looping or not
        self._loop_enabled = not self._loop_enabled

    def now(self):
        return self._head

    def play(self, direction=1.0):
        self._direction = direction

    def pause(self):
        self._direction = 0.0

    def stop(self):
        self.pause()
        self._head = self._start_time

    def set(self, timestamp):
        self._head = max(self._start_time, min(timestamp, self._end_time))

    def render(self, delta_t):

        if self._direction == 0.0:
            return

        # TODO: Consider action when abs(delta_t * self.__direction) > 2 * self.__duration
        self._head += delta_t * self._direction

        if self._head < self._start_time:
            # Play backward to the start time
            print("Play backward to the start time")
            if self._loop_enabled:
                self._head += self._duration
            else:
                self._head = self._start_time
                self.stop()
                return
        elif self._head > self._end_time:
            # Play forward to the end time
            print("Play forward to the end time")
            if self._loop_enabled:
                self._head -= self._duration
            else:
                self._head = self._duration
                self.stop()
                return


class TimelineWithSeries(Timeline):
    """Create timeline given a time series (list/tuple/np.array-like).
    Usage examples:
    >>> series = list(range(10))
    >>> timeline = TimelineWithSeries(series)
    >>> print(timeline.start, timeline.end, timeline.duration)
    0 9 9
    >>> timeline.series
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    >>> timeline.now()
    0
    >>> timeline.play(3.0)  # x2 speed
    >>> timeline.render(0.5)  # wall time, playback 0.5 * 3.0 for timeline actually
    >>> timeline.now()
    1.5
    >>> timeline.pause()  # set playback speed to 0
    >>> timeline.render(0.5)
    >>> timeline.now()
    1.5
    >>> timeline.stop()
    >>> timeline.now()
    0

    # Offset time series given new start time or end time
    >>> timeline.end = 5
    >>> print(timeline.start, timeline.end, timeline.duration)
    -4 5 9
    >>> timeline.series
    [-4, -3, -2, -1, 0, 1, 2, 3, 4, 5]
    >>> timeline.start = 2
    >>> print(timeline.start, timeline.end, timeline.duration)
    2 11 9
    >>> timeline.series
    [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

    # Modifying duration is not allowed since we have a time series to align
    >>> timeline.duration = 12
    Traceback (most recent call last):
      ...
    AttributeError: can't set attribute
    """
    __slots__ = ('_series', '_index')

    def __init__(self, series, loop_enabled=True):

        # Series
        self._series = series
        self._index = 0

        # Super class initialization
        start = series[0]
        duration = series[-1] - series[0]
        super().__init__(start, duration, loop_enabled)

    @property
    def start(self):
        return self._start_time

    @start.setter
    def start(self, value):
        offset = value - self._series[0]
        for idx in range(len(self._series)):
            self._series[idx] += offset
        self._start_time = self._series[0]
        self._end_time = self._series[-1]

    @property
    def end(self):
        return self._end_time

    @end.setter
    def end(self, value):
        offset = value - self._series[-1]
        for idx in range(len(self._series)):
            self._series[idx] += offset
        self._start_time = self._series[0]
        self._end_time = self._series[-1]

    @property
    def duration(self):
        """Override duration property to remove setter"""
        return self._duration

    @property
    def series(self):
        return self._series

    @series.setter
    def series(self, series):
        self._series = series
        self._index = 0
        self._start_time = series[0]
        self._end_time = series[-1]
        self._duration = series[-1] - series[0]

    @property
    def index(self):
        # Return the last index self.__head was
        return self._index

    @index.setter
    def index(self, idx=-1):
        assert isinstance(idx, int) and (idx == -1 or idx >= 0)
        if idx == -1:
            self._index = len(self._series) - 1

        self._index = idx

    def getTimestamp(self, index):
        return self.series[index]

    def getIndex(self, timestamp):
        # Support both list or np.array
        return bisect.bisect(self.series, timestamp) - 1

    def set(self, timestamp):
        self._index = self.getIndex(timestamp)
        self._head = timestamp
        # self._head = self._series[self._index]

    def render(self, delta_t):

        if self._direction == 0.0:
            return

        # TODO: Consider action when abs(delta_t * self.__direction) > 2 * self.__duration
        self._head += delta_t * self._direction

        if self._head < self._start_time:
            # Play backward to the start time
            print("Play backward to the start time")
            if self._loop_enabled:
                self._head += self._duration
                self._index = self.getIndex(self._head)
            else:
                self._head = self._start_time
                self._index = 0
                self.stop()
                return
        elif self._head > self._end_time:
            # Play forward to the end time
            print("Play forward to the end time")
            if self._loop_enabled:
                self._head -= self._duration
                self._index = self.getIndex(self._head)
            else:
                self._head = self._duration
                self._index = len(self._series) - 1
                self.stop()
                return


if __name__ == '__main__':
    import doctest
    doctest.testmod()
