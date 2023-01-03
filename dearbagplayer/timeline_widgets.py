import dearpygui.dearpygui as dpg
import os
import sys

script_abspath = os.path.split(os.path.realpath(__file__))[0]
sys.path.append(script_abspath)

try:
    import timeline
except:
    raise ModuleNotFoundError('Module timeline not found.')


class TimelineWidgets:
    """
    Create Timeline Wigets given Start Time and Duration

    Usage examples:

    # Init DearPyGui and create TimelineWidgets instance
    >>> dpg.create_context()
    >>> timeline_widget = TimelineWidgets()  # start_time=0, duration=0 by default

    # Set up DearPyGui window
    >>> with dpg.window(label="Timeline", tag="Primary Window"):
    ...     timeline_widget.createWidgets()
    >>> dpg.create_viewport(title="Timeline Test", height=400, width=600, x_pos=0, y_pos=0)
    >>> dpg.set_primary_window("Primary Window", True)
    >>> dpg.setup_dearpygui()
    >>> dpg.show_viewport()

    # Test properties
    >>> timeline_widget.start = 1
    >>> print(timeline_widget.start, timeline_widget.end, timeline_widget.duration)
    1 1.0 0.0
    >>> timeline_widget.duration = 5
    >>> print(timeline_widget.start, timeline_widget.end, timeline_widget.duration)
    1 6 5
    >>> timeline_widget.end = 3
    >>> print(timeline_widget.start, timeline_widget.end, timeline_widget.duration)
    1 3 2
    >>> timeline_widget.now()
    1.0
    >>> timeline_widget.play()  # default speed = 1.0
    >>> timeline_widget.render(1.2)
    >>> timeline_widget.now()
    2.2

    # Test widget running
    >>> import time; start = time.time()
    >>> while dpg.is_dearpygui_running():
    ...     timeline_widget.render(dpg.get_delta_time())
    ...     dpg.render_dearpygui_frame()
    ...     if time.time() - start > 3.0:
    ...         break
    >>> dpg.destroy_context()
    """
    __slots__ = ('__timeline', 'timeline_bar', 'timeline_bar2', 'head_updated', 'is_played',
                 'text_box', 'speed_box', 'play_button', 'pause_button', 'stop_button')

    def __init__(self, start_time=0.0, duration=0.0, loop_enabled=True):
        self.__timeline = timeline.Timeline(start_time, duration, loop_enabled)

        # Elements
        self.timeline_bar = None
        self.timeline_bar2 = None

        # Update
        self.head_updated = False
        self.is_played = False

    @property
    def start(self):
        return self.__timeline.start

    @start.setter
    def start(self, value):
        self.__timeline.start = value
        dpg.configure_item(self.timeline_bar2, min_value=self.__timeline.start)

    @property
    def end(self):
        return self.__timeline.end

    @end.setter
    def end(self, value):
        self.__timeline.end = value
        dpg.configure_item(self.timeline_bar2, max_value=self.__timeline.end)

    @property
    def duration(self):
        return self.__timeline.duration

    @duration.setter
    def duration(self, value):
        self.__timeline.duration = value

    def now(self):
        return self.__timeline.now()

    def resetLimits(self, min_t, max_t):
        self.__timeline.start = min_t
        self.__timeline.end = max_t
        dpg.configure_item(
            self.timeline_bar2, min_value=self.__timeline.start, max_value=self.__timeline.end
        )

    def createWidgets(self):
        with dpg.group(horizontal=True):
            self.timeline_bar = dpg.add_progress_bar(
                label="Timeline", overlay=f"{self.__timeline.start}/{self.__timeline.end}"
            )
            self.text_box = dpg.add_text(label="")

        self.timeline_bar2 = dpg.add_slider_float(
            label="", default_value=self.__timeline.start,
            min_value=self.__timeline.start, max_value=self.__timeline.end,
            callback=self.timelineSettingCb
        )
        with dpg.group(horizontal=True):
            self.speed_box = dpg.add_drag_float(
                label="Speed", default_value=1.0, min_value=-5.0, max_value=5.0,
                width=50, callback=self.speedCb
            )
            self.play_button = dpg.add_button(
                label="Play", arrow=True, direction=dpg.mvDir_Right, callback=self.playCb
            )
            self.pause_button = dpg.add_button(label="Pause", callback=self.pauseCb)
            self.stop_button = dpg.add_button(label="Stop", callback=self.stopCb)
            dpg.disable_item(self.pause_button)

    def timelineSettingCb(self, sender, app_data, user_data):
        cur_time = app_data
        self.__timeline.set(cur_time)
        dpg.set_value(self.timeline_bar, (cur_time - self.__timeline.start) / self.__timeline.duration)
        self.head_updated = True

    def speedCb(self, sender, app_data, user_data):
        if not dpg.is_item_enabled(self.play_button):
            self.__timeline.play(dpg.get_value(self.speed_box))

    def playCb(self, sender, app_data, user_data):
        self.play()

    def pauseCb(self, sender, app_data, user_data):
        self.pause()

    def stopCb(self, sender, app_data, user_data):
        self.stop()

    def play(self):
        self.is_played = True
        self.__timeline.play(dpg.get_value(self.speed_box))
        if dpg.is_item_enabled(self.play_button):
            # print("Play Disabled!")
            dpg.disable_item(self.play_button)
            dpg.enable_item(self.pause_button)
            dpg.enable_item(self.stop_button)

    def pause(self):
        self.is_played = False
        self.__timeline.pause()
        if dpg.is_item_enabled(self.pause_button):
            # print("Play Disabled!")
            dpg.disable_item(self.pause_button)
            dpg.enable_item(self.play_button)
            dpg.enable_item(self.stop_button)

    def stop(self):
        self.is_played = False
        self.__timeline.stop()
        if dpg.is_item_enabled(self.stop_button):
            # print("Stop Disabled!")
            dpg.disable_item(self.stop_button)
            dpg.disable_item(self.pause_button)
            dpg.enable_item(self.play_button)

    def isPlayed(self):
        return self.is_played

    def resetHeadUpdated(self):
        self.head_updated = False

    def updateTimeline(self, now):
        if self.timeline_bar and self.timeline_bar2:
            if self.__timeline.duration == 0.0:
                dpg.set_value(self.timeline_bar, 0.0)
            else:
                dpg.set_value(self.timeline_bar, (now - self.__timeline.start) / self.__timeline.duration)
            dpg.set_value(self.timeline_bar2, now)
            dpg.configure_item(self.timeline_bar, overlay=f"{now:.02f}/{self.__timeline.end:.02f}")
            dpg.configure_item(self.text_box, default_value=f"{now:.02f}/{self.__timeline.end:.02f}")

    def render(self, delta_time):
        # Timeline render
        self.__timeline.render(delta_time)
        self.updateTimeline(self.__timeline.now())


class TimelineWidgetsWithSeries(TimelineWidgets):
    """
    Create Timeline Wigets from Time Series

    Usage examples:

    # Init DearPyGui and create TimelineWidgetsWithSeries instance
    >>> dpg.create_context()
    >>> import numpy as np
    >>> series = np.linspace(0.0, 10.0, 50)
    >>> timeline_widget = TimelineWidgetsWithSeries(series)

    # Set up DearPyGui window
    >>> with dpg.window(label="Timeline-Series", tag="Primary Window 2"):
    ...     timeline_widget.createWidgets()
    >>> dpg.create_viewport(title="Timeline-Series Test", height=400, width=600, x_pos=0, y_pos=0)
    >>> dpg.set_primary_window("Primary Window 2", True)
    >>> dpg.setup_dearpygui()
    >>> dpg.show_viewport()

    # Test properties
    >>> timeline_widget.start = 1
    >>> print(timeline_widget.start, timeline_widget.end, timeline_widget.duration)
    1.0 11.0 10.0
    >>> timeline_widget.duration = 5
    Traceback (most recent call last):
      ...
    AttributeError: can't set attribute
    >>> timeline_widget.end = 3
    >>> print(timeline_widget.start, timeline_widget.end, timeline_widget.duration)
    -7.0 3.0 10.0
    >>> timeline_widget.now()
    0.0
    >>> timeline_widget.play()  # default speed = 1.0
    >>> timeline_widget.render(1.2)
    >>> timeline_widget.now()
    1.2

    # Test widget running
    >>> import time; start = time.time()
    >>> while dpg.is_dearpygui_running():
    ...     timeline_widget.render(dpg.get_delta_time())
    ...     dpg.render_dearpygui_frame()
    ...     if time.time() - start > 3.0:
    ...         break
    >>> dpg.destroy_context()
    """

    def __init__(self, series, loop_enabled=True):
        self.__timeline = timeline.TimelineWithSeries(series, loop_enabled)

        # Super class initialization
        start = series[0]
        duration = series[-1] - series[0]
        super().__init__(start, duration, loop_enabled)

    @property
    def start(self):
        return self.__timeline.start

    @start.setter
    def start(self, value):
        self.__timeline.start = value
        dpg.configure_item(
            self.timeline_bar2, min_value=self.__timeline.start, max_value=self.__timeline.end
        )

    @property
    def end(self):
        return self.__timeline.end

    @end.setter
    def end(self, value):
        self.__timeline.end = value
        dpg.configure_item(
            self.timeline_bar2, min_value=self.__timeline.start, max_value=self.__timeline.end
        )

    @property
    def duration(self):
        """Override property to remove setter"""
        return self.__timeline.duration

    @property
    def index(self):
        return self.__timeline.index

    def getTimestamp(self, index):
        return self.__timeline.getTimestamp(index)

    def getIndex(self, timestamp):
        return self.__timeline.getIndex(timestamp)


if __name__ == "__main__":
    import doctest
    doctest.testmod()
