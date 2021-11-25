import bisect

class Timeline():

    def __init__(self, start_time=0.0, duration=0.0, loop_enabled=True):

        # Duration of the timeline
        self.__duration = duration

        # Start and end time (not used yet)
        self.__start_time = start_time
        self.__end_time = self.__start_time + self.__duration

        # Current timestamp (head)
        self.__head = self.__start_time

        # Direction (forward/backward) * playback speed
        self.__direction = 0.0

        # Enable/Disable looped playback
        self.__loop_enabled = loop_enabled

    def loop(self):
        # Toggle looping or not
        self.__loop_enabled = not self.__loop_enabled

    def now(self):
        return self.__head

    @property
    def start(self):
        return self.__start_time

    @start.setter
    def start(self, value):
        self.__start_time = value
        self.__end_time = self.__start_time + self.__duration

    @property
    def end(self):
        return self.__end_time

    @end.setter
    def end(self, value):
        assert value > self.__start_time
        self.__end_time = value
        self.__duration = self.__end_time - self.__start_time

    @property
    def duration(self):
        return self.__duration

    @duration.setter
    def duration(self, value):
        assert value > 0
        self.__duration = value
        self.__end_time = self.__start_time + self.__duration

    def play(self, direction=1.0):
        self.__direction = direction

    def pause(self):
        self.__direction = 0.0

    def stop(self):
        self.pause()
        self.__head = self.__start_time

    def set(self, timestamp):
        self.__head = max(self.__start_time, min(timestamp, self.__end_time))

    def render(self, delta_t):

        if self.__direction == 0.0:
            return

        # TODO: Consider action when abs(delta_t * self.__direction) > 2 * self.__duration
        self.__head += delta_t * self.__direction

        if self.__head < self.__start_time:
            # Play backward to the start time
            print("Play backward to the start time")
            if self.__loop_enabled:
                self.__head += self.__duration
            else:
                self.__head = self.__start_time
                self.stop()
                return
        elif self.__head > self.__end_time:
            # Play forward to the end time
            print("Play forward to the end time")
            if self.__loop_enabled:
                self.__head -= self.__duration
            else:
                self.__head = self.__duration
                self.stop()
                return

class TimelineWithSeries(Timeline):

    def __init__(self, series, loop_enabled=True):

        # Series
        self.__series = series
        self.__index = 0

        # Super class initialization
        start = series[0]
        duration = series[-1] - series[0]
        super().__init__(start, duration, loop_enabled)


    @property
    def series(self):
        return self.__series

    @series.setter
    def series(self, series):
        self.__series = series
        self.start = series[0]
        self.duration = series[-1] - series[0]

    @property
    def index(self):
        # Return the last index self.__head was
        return self.__index

    @index.setter
    def index(self, idx=-1):
        assert isinstance(idx, int) and (idx == -1 or idx >= 0)
        if idx == -1:
            self.__index = len(self.series) - 1

        self.__index = idx

    def getTimestamp(self, index):
        return self.__series[index]

    def getIndex(self, timestamp):
        # Support both list or np.array
        return bisect.bisect(self.__series, timestamp) - 1

    def set(self, timestamp):
        self.__index = self.getIndex(timestamp)
        self.__head = timestamp
        # self.__head = self.__series[self.__index]

    def render(self, delta_t):

        if self.__direction == 0.0:
            return

        # TODO: Consider action when abs(delta_t * self.__direction) > 2 * self.__duration
        self.__head += delta_t * self.__direction

        if self.__head < self.__start_time:
            # Play backward to the start time
            print("Play backward to the start time")
            if self.__loop_enabled:
                self.__head += self.__duration
                self.__index = self.getIndex(self.__head)
            else:
                self.__head = self.__start_time
                self.__index = 0
                self.stop()
                return
        elif self.__head > self.__end_time:
            # Play forward to the end time
            print("Play forward to the end time")
            if self.__loop_enabled:
                self.__head -= self.__duration
                self.__index = self.getIndex(self.__head)
            else:
                self.__head = self.__duration
                self.__index = len(self.__series) - 1
                self.stop()
                return

