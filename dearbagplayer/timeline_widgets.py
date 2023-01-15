"""
Copyright (c) 2021-2022, Wei Wang <wei.wang.bit@outlook.com>

Timeline Widgets based on DearPyGui:
- TimelineWidgets
- TimelineWidgetsWithSeries
"""

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
    """Create Timeline Wigets given Start Time and Duration

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
    >>> timeline_widget.resetLimits(0.5, 2.4)
    >>> print(timeline_widget.start, timeline_widget.end, timeline_widget.duration)
    0.5 2.4 1.9
    >>> timeline_widget.play()  # default speed = 1.0
    >>> timeline_widget.render(1.2)
    >>> timeline_widget.now()
    1.7

    >>> timeline_widget.is_stopped = False
    Traceback (most recent call last):
        ...
    AttributeError: can't set attribute
    >>> timeline_widget.is_played = False
    Traceback (most recent call last):
        ...
    AttributeError: can't set attribute
    >>> timeline_widget.head_updated = False
    Traceback (most recent call last):
        ...
    AttributeError: can't set attribute
    >>> timeline_widget.resetHeadUpdated()
    >>> timeline_widget.resetIsStopped()

    # Test widget running
    >>> import time; start = time.time()
    >>> while dpg.is_dearpygui_running():
    ...     timeline_widget.render(dpg.get_delta_time())
    ...     dpg.render_dearpygui_frame()
    ...     if time.time() - start > 3.0:
    ...         break
    >>> dpg.destroy_context()
    """
    __slots__ = ('_timeline', 'timeline_bar', 'timeline_bar2', '_head_updated', '_is_played', '_is_stopped',
                 'text_box', 'speed_box', 'play_button', 'pause_button', 'stop_button', 'loop_checkbox')

    def __init__(self, start_time=0.0, duration=0.0, loop_enabled=True):
        self._timeline = timeline.Timeline(start_time, duration, loop_enabled)

        # Elements
        self.timeline_bar = None
        self.timeline_bar2 = None

        # Update
        self._head_updated = False
        self._is_played = False
        self._is_stopped = False

    @property
    def start(self):
        return self._timeline.start

    @start.setter
    def start(self, value):
        self._timeline.start = value
        dpg.configure_item(self.timeline_bar2, min_value=self._timeline.start)

    @property
    def end(self):
        return self._timeline.end

    @end.setter
    def end(self, value):
        self._timeline.end = value
        dpg.configure_item(self.timeline_bar2, max_value=self._timeline.end)

    @property
    def duration(self):
        return self._timeline.duration

    @duration.setter
    def duration(self, value):
        self._timeline.duration = value

    @property
    def head_updated(self):
        return self._head_updated

    @property
    def is_played(self):
        return self._is_played

    @property
    def is_stopped(self):
        return self._is_stopped

    def resetHeadUpdated(self):
        self._head_updated = False

    def resetIsStopped(self):
        self._is_stopped = False

    def now(self):
        return self._timeline.now()

    def resetLimits(self, min_t, max_t):
        self._timeline.start = min_t
        self._timeline.end = max_t
        dpg.configure_item(
            self.timeline_bar2, min_value=self._timeline.start, max_value=self._timeline.end
        )

    def createWidgets(self):
        with dpg.group(horizontal=True):
            self.timeline_bar = dpg.add_progress_bar(
                label="Timeline", overlay=f"{self._timeline.start}/{self._timeline.end}"
            )
            self.text_box = dpg.add_text(label="")

        self.timeline_bar2 = dpg.add_slider_float(
            label="", default_value=self._timeline.start,
            min_value=self._timeline.start, max_value=self._timeline.end,
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
            self.loop_checkbox = dpg.add_checkbox(label="Play in loop", callback=self.loopCb,
                                                  default_value=self._timeline.loop_enabled)
            dpg.disable_item(self.pause_button)

    def timelineSettingCb(self, sender, app_data, user_data):
        cur_time = app_data
        self._timeline.set(cur_time)
        dpg.set_value(self.timeline_bar, (cur_time - self._timeline.start) / self._timeline.duration)
        self._head_updated = True

    def speedCb(self, sender, app_data, user_data):
        if not dpg.is_item_enabled(self.play_button):
            self._timeline.play(dpg.get_value(self.speed_box))

    def playCb(self, sender, app_data, user_data):
        self.play()

    def pauseCb(self, sender, app_data, user_data):
        self.pause()

    def stopCb(self, sender, app_data, user_data):
        self.stop()

    def loopCb(self, sender, app_data, user_data):
        self._timeline.loop_enabled = app_data

    def play(self):
        if self._timeline.duration == 0.0:
            return
        self._is_played = True
        self._is_stopped = False
        self._timeline.play(dpg.get_value(self.speed_box))
        if dpg.is_item_enabled(self.play_button):
            # print("Play Disabled!")
            dpg.disable_item(self.play_button)
            dpg.enable_item(self.pause_button)
            dpg.enable_item(self.stop_button)

    def pause(self):
        self._is_played = False
        self._is_stopped = False
        self._timeline.pause()
        if dpg.is_item_enabled(self.pause_button):
            # print("Play Disabled!")
            dpg.disable_item(self.pause_button)
            dpg.enable_item(self.play_button)
            dpg.enable_item(self.stop_button)

    def stop(self):
        self._is_played = False
        self._is_stopped = True
        self._timeline.stop()
        if dpg.is_item_enabled(self.stop_button):
            # print("Stop Disabled!")
            dpg.disable_item(self.stop_button)
            dpg.disable_item(self.pause_button)
            dpg.enable_item(self.play_button)

    def updateTimeline(self, now):
        if self.timeline_bar and self.timeline_bar2:
            if self._timeline.duration == 0.0:
                dpg.set_value(self.timeline_bar, 0.0)
            else:
                dpg.set_value(self.timeline_bar, (now - self._timeline.start) / self._timeline.duration)
            dpg.set_value(self.timeline_bar2, now)
            dpg.configure_item(self.timeline_bar, overlay=f"{now:.02f}/{self._timeline.end:.02f}")
            dpg.configure_item(self.text_box, default_value=f"{now:.02f}/{self._timeline.end:.02f}")

            # Stop when not play in loop and timeline is over
            if self.is_played and not self._timeline.loop_enabled and self._timeline.speed == 0.0:
                self.stop()

    def render(self, delta_time):
        # Timeline render
        self._timeline.render(delta_time)
        self.updateTimeline(self._timeline.now())


class TimelineWidgetsWithSeries(TimelineWidgets):
    """Create Timeline Wigets from Time Series.

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
    -7.0
    >>> timeline_widget.play()  # default speed = 1.0
    >>> timeline_widget.render(1.2)
    >>> timeline_widget.now()
    -5.8

    >>> timeline_widget.is_stopped = False
    Traceback (most recent call last):
        ...
    AttributeError: can't set attribute
    >>> timeline_widget.is_played = False
    Traceback (most recent call last):
        ...
    AttributeError: can't set attribute
    >>> timeline_widget.head_updated = False
    Traceback (most recent call last):
        ...
    AttributeError: can't set attribute
    >>> timeline_widget.resetHeadUpdated()
    >>> timeline_widget.resetIsStopped()

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
        # Super class initialization
        start = series[0]
        duration = series[-1] - series[0]
        super().__init__(start, duration, loop_enabled)

        # Override timeline instance
        self._timeline = timeline.TimelineWithSeries(series, loop_enabled)

    @property
    def start(self):
        return self._timeline.start

    @start.setter
    def start(self, value):
        self._timeline.start = value
        dpg.configure_item(
            self.timeline_bar2, min_value=self._timeline.start, max_value=self._timeline.end
        )

    @property
    def end(self):
        return self._timeline.end

    @end.setter
    def end(self, value):
        self._timeline.end = value
        dpg.configure_item(
            self.timeline_bar2, min_value=self._timeline.start, max_value=self._timeline.end
        )

    @property
    def duration(self):
        """Override property to remove setter"""
        return self._timeline.duration

    @property
    def index(self):
        return self._timeline.index

    def getTimestamp(self, index):
        return self._timeline.getTimestamp(index)

    def getIndex(self, timestamp):
        return self._timeline.getIndex(timestamp)

if __name__ == "__main__":
    import doctest
    doctest.testmod()
