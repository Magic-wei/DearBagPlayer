"""
Copyright (c) 2021-2022, Wei Wang <wei.wang.bit@outlook.com>

DearBagPlayer Application
"""

import os
import sys

script_abspath = os.path.split(os.path.realpath(__file__))[0]
sys.path.append(script_abspath)

try:
    import timeline_widgets
except:
    raise ModuleNotFoundError('Module timeline_widgets not found.')

import dearpygui.dearpygui as dpg
import rosbag
import numpy as np
import time
import bisect

import yaml
from yaml.loader import SafeLoader


class DearBagPlayer:

    def __init__(self, topics=None):
        # Bag info
        self.bag_files = list()
        self.bag_files_name = list()

        # Data
        self.data_pool_window = None
        self.topics = topics
        self.msg_data_pool = list()

        # Plots
        self.xy_plot_enabled = False
        self.s_length_plot_enabled = False

        # Timeline
        self.min_time = 0.0
        self.max_time = 0.0
        self.__timeline = timeline_widgets.TimelineWidgets(start_time=0.0, duration=0.0, loop_enabled=True)

        # Time series control
        self.start_time = 0.0
        self.__index = 0
        self.__head = 0.0
        self.vlines = None
        self.xypoints = None

        # Series selector
        self.tab_bar = None

    def initTimeline(self):
        self.max_time = 0.0
        self.min_time = 1e19
        for database in self.msg_data_pool:
            for topic in database.keys():
                if self.min_time > database[topic]["timestamp"][0]:
                    self.min_time = database[topic]["timestamp"][0]
                if self.max_time < database[topic]["timestamp"][-1]:
                    self.max_time = database[topic]["timestamp"][-1]
        self.__timeline.start = self.min_time
        self.__timeline.end = self.max_time

    def getTopic(self, bag_file, topics):
        # Read bag
        bag = rosbag.Bag(bag_file)

        # Topic check
        if topics is not None:
            # Check if topics are in the rosbag
            def checkTopic(topics):
                info = bag.get_type_and_topic_info()
                topic_list = list(info[1].keys())
                for topic in topics:
                    if topic not in topic_list:
                        return False

                # the rosbag contains all the topics listed
                return True

            if not checkTopic(topics):
                bag.close()
                raise ValueError('At least one given topic not found in rosbag!')

        """
        msg_data = {
            "topic01": {
                "timestamp": np.array([]),
                ...
            }
            "topic02": {
                "timestamp": np.array([]),
                ...
            }
        }
        """

        # Get all topic names and msg types
        info_dict = yaml.load(bag._get_yaml_info(), Loader=SafeLoader)
        msg_data = dict()
        for topic_info in info_dict["topics"]:
            topic = topic_info["topic"]
            if topics is not None:
                if topic in topics:
                    msg_data[topic] = dict()
            else:
                msg_data[topic] = dict()

        def addMsgData(topic, key, data):
            if key in msg_data[topic].keys():
                # TODO: list.append() is much faster than np.append()
                msg_data[topic][key] = np.append(msg_data[topic][key], data)
            else:
                msg_data[topic][key] = np.array([data])

        for topic, msg, t in bag.read_messages(topics=topics):
            # Extract msg struct
            def getSlotStruct(msg):
                if checkEndStatus(msg):
                    return msg

                return dict().fromkeys(msg.__slots__)

            def checkEndStatus(msg):
                if hasattr(msg, "__slots__"):
                    # print(f"[checkEndStatus] {msg} still has children!")
                    return False

                # print(f"[checkEndStatus] {msg} found built-in type in [int, float, bool, str, list, tuple], End!")
                return True

            def name_join(upper, lower):
                if not upper:
                    return str(lower)
                if upper[-1] == '/':
                    return upper + str(lower)
                return upper + '/' + str(lower)
                # return os.path.join(ns, name)

            # TODO: improve speed of entities calculation
            def getMsgData(msg, upper):
                # Check if reach end level
                base_slots = getSlotStruct(msg)
                if base_slots is msg:
                    # Reach end level
                    if isinstance(msg, list) or isinstance(msg, tuple):
                        length = len(msg)
                        base_slots = dict()
                        for k in range(0, length):
                            base_slots[k] = msg[k]

                        entities = list(base_slots.keys())
                        for k in range(0, length):
                            entities[k] = name_join(upper, k)
                            addMsgData(topic, entities[k], msg[k])
                        return base_slots, entities
                    elif isinstance(msg, bool):
                        addMsgData(topic, upper, int(msg))
                        return base_slots, upper
                    else:
                        # int, float, str types
                        addMsgData(topic, upper, msg)
                        return base_slots, upper
                else:
                    # Still has children, base_slots is dict, call getMsgData again
                    entities = list(base_slots.keys())
                    entities_out = list()
                    for key in base_slots.keys():
                        idx = entities.index(key)
                        entities[idx] = name_join(upper, key)
                        sub_msg = getattr(msg, key)
                        base_slots[key], entities_new = getMsgData(sub_msg, entities[idx])
                        if isinstance(entities_new, list):
                            entities_out = entities_out + entities_new
                        else:
                            entities_out.append(entities_new)
                    return base_slots, entities_out

            # Full data extraction
            getMsgData(msg, topic)

            # Timestamp
            timestamp = t.secs + t.nsecs * pow(10, -9)
            if 'std_msgs/Header' in msg._get_types():
                timestamp = msg.header.stamp.secs + msg.header.stamp.nsecs * pow(10, -9)
            addMsgData(topic, "timestamp", timestamp)

        # Align timestamp
        timestamp_min = np.inf
        for topic in msg_data.keys():
            timestamp_min = min(timestamp_min, msg_data[topic]["timestamp"][0])

        for topic in msg_data.keys():
            msg_data[topic]["timestamp"] -= timestamp_min

        # Close bag
        bag.close()
        print("Data loaded!")

        # Return
        return msg_data

    # -----------------------------------------
    # Update
    # -----------------------------------------

    def update(self):
        self.timelineUpdate()
        self.curPointUpdate()
        self.checkLastPlotTab()

    def timelineUpdate(self):
        # Update head, index, and rendering
        if self.__timeline.head_updated:
            # Manually set head
            self.__timeline.resetHeadUpdated()

        delta_time = dpg.get_delta_time()
        self.__timeline.render(delta_time)
        self.__head = self.__timeline.now()

    def curPointUpdate(self):
        """
        TODO: Consider multiple timelines for multiple topics
        """
        if self.__timeline.is_played or self.__timeline.is_stopped:
            if len(self.msg_data_pool) == 0:
                return
            self.vlinesTimeUpdate(self.__timeline.now())
            self.xypointsUpdate()
            if self.__timeline.is_stopped:
                self.__timeline.resetIsStopped()

    def vlinesTimeUpdate(self, timestamp):
        if not self.vlines:
            self.createTimeLines()

        for vline in self.vlines:
            # TODO: Figure out why built-in float type get errors
            dpg.set_value(vline, [np.float64(timestamp)])

    def xypointsUpdate(self):
        if not self.xypoints:
            self.createTimePoints()

        total_index = 0
        last_user_data_length = 0
        last_yaxis = None
        for xypoint in self.xypoints:
            yaxis = dpg.get_item_info(xypoint)['parent']
            if last_yaxis is not None and last_yaxis != yaxis:
                total_index += last_user_data_length
            user_data = dpg.get_item_user_data(yaxis)
            xy_index = self.xypoints.index(xypoint) - total_index
            topic = user_data[xy_index][3]
            bag_name = user_data[xy_index][4]
            bag_index = self.bag_files_name.index(bag_name)
            index = self.getIndex(self.msg_data_pool[bag_index][topic]["timestamp"], self.__timeline.now())
            # timestamp = self.msg_data_pool[0][topic]["timestamp"][index]
            dpg.set_value(xypoint, [user_data[xy_index][0][index], user_data[xy_index][1][index]])

            last_user_data_length = len(user_data)
            last_yaxis = yaxis

    def getIndex(self, time_series, timestamp):
        # Support both list or np.array
        return bisect.bisect(time_series, timestamp) - 1

    def checkLastPlotTab(self):
        """
        Check if last plot tab is closed. If yes, create a new one.
        """
        self.deleteClosedTab()
        if len(dpg.get_item_children(self.tab_bar)[1]) == 1:
            self.addPlotPageCb("Add Plot Button", None, None)

    # -----------------------------------------
    # Plots
    # -----------------------------------------

    def clearTimeLinesAndPoints(self):
        if self.vlines is not None:
            for vline in self.vlines:
                dpg.delete_item(vline)

        if self.xypoints is not None:
            for xypoint in self.xypoints:
                dpg.delete_item(xypoint)

        self.vlines = None
        self.xypoints = None

    def createTimeLines(self):
        # Check if act_plot is deleted by users
        try:
            dpg.get_item_info(dpg.get_item_user_data(self.tab_bar)['act_plot'])
        except:
            return

        act_plot = dpg.get_item_user_data(self.tab_bar)['act_plot']
        plots = dpg.get_item_info(act_plot)['children'][1]

        self.vlines = list()

        for plot in plots:
            yaxis = dpg.get_item_info(plot)['children'][1][1]
            if dpg.get_item_user_data(yaxis) is None:
                vline_tag = dpg.add_vline_series([0.0], parent=yaxis)
                self.vlines.append(vline_tag)

    def createTimePoints(self):
        # Check if act_plot is deleted by users
        try:
            dpg.get_item_info(dpg.get_item_user_data(self.tab_bar)['act_plot'])
        except:
            return

        act_plot = dpg.get_item_user_data(self.tab_bar)['act_plot']
        plots = dpg.get_item_info(act_plot)['children'][1]

        self.xypoints = list()

        for plot in plots:
            yaxis = dpg.get_item_info(plot)['children'][1][1]
            if dpg.get_item_user_data(yaxis):
                for k in range(0, len(dpg.get_item_user_data(yaxis))):
                    scatter_tag = dpg.add_scatter_series([0], [0], parent=yaxis)
                    self.xypoints.append(scatter_tag)

    def _fitAxesData(self, plot):
        yaxis = dpg.get_item_info(plot)["children"][1][0]
        xaxis = dpg.get_item_info(plot)["children"][1][1]
        dpg.fit_axis_data(yaxis)
        dpg.fit_axis_data(xaxis)

    def _resetValue(self):
        length = len(dpg.get_item_user_data(self.data_pool_window))
        for i in range(0, length):
            item = dpg.get_item_user_data(self.data_pool_window)[length - 1 - i]
            dpg.set_value(item, False)
            dpg.get_item_user_data(self.data_pool_window).remove(item)

    def commonDropCallback(self, yaxis, app_data):

        if self.xy_plot_enabled:
            # X-Y plot with two time series

            datax = dpg.get_item_user_data(app_data[0])
            datay = dpg.get_item_user_data(app_data[1])

            # Check they belongs to the same topic and bag
            if datax[3] != datay[3] or datax[4] != datay[4]:
                # TODO: use popup and return instead of Exception
                raise ValueError("XY plot must comes from the same bag and topic!")

            # Plot line series
            bag_name = os.path.splitext(datax[4])[0]
            label = bag_name + ":" + datax[2] + "," + datay[2][-1]
            dpg.add_line_series(datax[1], datay[1], label=label, parent=yaxis)

            # Add button to legend right click bar
            self.addLegendClickedMenu(dpg.last_item())

            old_user_data = dpg.get_item_user_data(yaxis)
            if old_user_data is None:
                old_user_data = list()
            new_user_data = old_user_data + [[datax[1], datay[1], label, datax[3], datax[4]]]  # topic, bag_name
            dpg.configure_item(yaxis, user_data=new_user_data)
            # print(dpg.get_item_user_data(yaxis))

        elif self.s_length_plot_enabled:
            # Data vs. arc-length plot

            datax = dpg.get_item_user_data(app_data[0])
            datay = dpg.get_item_user_data(app_data[1])
            # Check they belongs to the same topic and bag
            if datax[3] != datay[3] or datax[4] != datay[4]:
                # TODO: use popup and return instead of Exception
                raise ValueError("Data vs. s plot must comes from the same bag and topic!")

            # Plot line series
            bag_name = os.path.splitext(datax[4])[0]
            label = bag_name + ":" + datay[2] + " vs. s"
            dpg.add_line_series(datax[1], datay[1], label=label, parent=yaxis)

            # Add button to legend right click bar
            self.addLegendClickedMenu(dpg.last_item())

            old_user_data = dpg.get_item_user_data(yaxis)
            if old_user_data is None:
                old_user_data = list()
            new_user_data = old_user_data + [[datax[1], datay[1], label, datax[3], datax[4]]]  # topic, bag_name
            dpg.configure_item(yaxis, user_data=new_user_data)
            # print(dpg.get_item_user_data(yaxis))

        else:
            # Data vs. time plots

            for item in app_data:
                data = dpg.get_item_user_data(item)
                bag_name = os.path.splitext(data[4])[0]
                label = bag_name + ":" + data[2]
                dpg.add_line_series(data[0], data[1], label=label, parent=yaxis)
                # Add button to legend right click bar
                self.addLegendClickedMenu(dpg.last_item())

        # Clean drop data & fit plot regions
        self._resetValue()
        self._fitAxesData(dpg.get_item_info(yaxis)["parent"])

    def addLegendClickedMenu(self, series_tag):
        # Add button to legend right click bar
        dpg.add_button(label="Delete Selected Series", user_data=series_tag, parent=series_tag,
                       callback=self.deleteSelectedSeriesCb)
        dpg.add_button(label="Delete All Series", user_data=series_tag, parent=series_tag,
                       callback=self.deleteAllSeriesCb)

    def deleteSelectedSeriesCb(self, sender, app_data, user_data):
        """user_data stores the tag of selected series"""
        dpg.delete_item(user_data)

    def deleteAllSeriesCb(self, sender, app_data, user_data):
        """user_data stores the tag of selected series"""
        plot = dpg.get_item_parent(user_data)
        dpg.delete_item(plot, children_only=True)

    def plotDropCallback(self, sender, app_data, user_data):
        yaxis = dpg.get_item_info(sender)["children"][1][1]
        self.commonDropCallback(yaxis, app_data)

    def axisDropCallback(self, sender, app_data, user_data):
        self.commonDropCallback(sender, app_data)

    def dragTopicPayloadCb(self, sender, app_data, user_data):
        """
        :param sender: dragged selectable item (topic)
        :param app_data: list of selected items (topics) in data pool
        :param user_data: None
        """
        # Append item if not selected
        if sender not in app_data:
            app_data.append(sender)

        # Update payload text
        payload = dpg.get_item_children(sender, slot=3)[0]
        payload_text = dpg.get_item_children(payload)[1][0]
        dpg.configure_item(
            payload_text,
            default_value=f"{len(app_data)} series to plot"
        )

    def addPlot(self, title="", x_label="", y_label="", height=200, width=300,
                equal_aspects=False, drop_plot_enabled=True):
        
        if drop_plot_enabled:
            plot_drop_callback = self.plotDropCallback
            axis_drop_callback = self.axisDropCallback
        else:
            plot_drop_callback = None
            axis_drop_callback = None

        with dpg.plot(label=title, height=height, width=width, equal_aspects=equal_aspects,
                      payload_type="plotting", drop_callback=plot_drop_callback):
            dpg.add_plot_legend()
            dpg.add_plot_axis(dpg.mvXAxis, label=x_label)
            dpg.add_plot_axis(dpg.mvYAxis, label=y_label, payload_type="plotting",
                              drop_callback=axis_drop_callback)

    def addPlotWithParent(self, parent, title="", x_label="", y_label="", height=200, width=300,
                    equal_aspects=False, drop_plot_enabled=True):

        if drop_plot_enabled:
            plot_drop_callback = self.plotDropCallback
            axis_drop_callback = self.axisDropCallback
        else:
            plot_drop_callback = None
            axis_drop_callback = None

        plot_tag = dpg.add_plot(
            label=title, height=height, width=width, equal_aspects=equal_aspects, payload_type="plotting",
            drop_callback=plot_drop_callback, parent=parent,
        )
        dpg.add_plot_legend(parent=plot_tag)
        dpg.add_plot_axis(dpg.mvXAxis, label=x_label, parent=plot_tag)
        dpg.add_plot_axis(dpg.mvYAxis, label=y_label, payload_type="plotting",
                          parent=plot_tag, drop_callback=axis_drop_callback)

        return plot_tag

    def createSubplots(self, rows=1, columns=1):
        with dpg.subplots(rows=rows, columns=columns, no_title=True, height=600, width=800, no_resize=False):
            self.addPlot()

    # -----------------------------------------
    # Plot Canvas Control Board
    # -----------------------------------------

    def addPlotPageCb(self, sender, app_data, user_data):
        dpg.get_item_user_data(self.tab_bar)['plot_pages'] += 1
        with dpg.tab(label=f"Plot {dpg.get_item_user_data(self.tab_bar)['plot_pages']}",
                     parent=self.tab_bar, closable=True) as tab_tag:
            dpg.bind_item_handler_registry(tab_tag, "tab_clicked_handler")
            self.createSubplots()

    def tabClickedMenuCb(self, sender, app_data, user_data):
        """
        :param sender: tab_bar
        :param app_data: [clicked_mouse_button (0-left, 1-right, 2-middle), clicked_tab]
        :param user_data: None
        """
        pos = dpg.get_mouse_pos(local=False)
        if app_data[0] == 1:  # right-clicked
            with dpg.window(pos=pos, min_size=[70, 15], popup=True, autosize=False):
                dpg.add_button(label="Rename", user_data=(app_data[1], pos), callback=self.renamePlotTabCb)

    def renamePlotTabCb(self, sender, app_data, user_data):
        """
        :param sender: Rename button
        :param app_data: None
        :param user_data: [clicked_tab, clicked_pos (x, y)]
        """
        pos = user_data[1]
        with dpg.window(pos=pos, min_size=[120, 15], no_title_bar=True, no_scrollbar=True) as rename_win:
            dpg.add_input_text(label="", hint="<new name>", on_enter=True,
                               user_data=(user_data[0], rename_win),
                               callback=self.renameWindowCb)
            dpg.focus_item(dpg.last_item())

    def renameWindowCb(self, sender, app_data, user_data):
        """
        :param sender: input_text item
        :param app_data: New name of the tab
        :param user_data: (tab_to_rename, rename_win)
        """
        dpg.configure_item(user_data[0], label=app_data)
        dpg.delete_item(user_data[1])  # delete rename window

    def splitHorizontallyCb(self, sender, app_data, user_data):
        subplots = dpg.get_item_user_data(self.tab_bar)['act_plot']
        cols = dpg.get_item_configuration(subplots)['cols']
        rows = dpg.get_item_configuration(subplots)['rows']
        plots = dpg.get_item_children(subplots)[1]
        for row in range(rows):
            plot_tag = self.addPlotWithParent(subplots)
            plots.insert(cols * (rows - row), plot_tag)
        dpg.reorder_items(subplots, 1, plots)
        dpg.configure_item(subplots, columns=cols + 1)

    def splitVerticallyCb(self, sender, app_data, user_data):
        subplots = dpg.get_item_user_data(self.tab_bar)['act_plot']
        cols = dpg.get_item_configuration(subplots)['cols']
        rows = dpg.get_item_configuration(subplots)['rows']
        for col in range(cols):
            self.addPlotWithParent(subplots)
        dpg.configure_item(subplots, rows=rows + 1)

    def clearCb(self, sender, app_data, user_data):
        self.__timeline.stop()
        self.clearTimeLinesAndPoints()
        act_plot = dpg.get_item_user_data(self.tab_bar)['act_plot']
        plots = dpg.get_item_info(act_plot)['children'][1]
        for plot in plots:
            xaxis = dpg.get_item_info(plot)['children'][1][0]
            yaxis = dpg.get_item_info(plot)['children'][1][1]
            dpg.delete_item(xaxis, children_only=True)
            dpg.delete_item(yaxis, children_only=True)

    def updateActCb(self, sender, app_data, user_data):
        """
        Triggered when activated tab is changed.

        Actions that won't trigger this callback function:
        - Create a new tab by clicking the '+' button
        - Delete a tab that is not activated
        - Delete the last tab

        :param sender: tag of the tab_bar
        :param app_data: the activated tab
        :param user_data: {"act_tab": tag, "act_plot": tag, "plot_pages": int}
        """
        self.deleteClosedTab()
        self.clearTimeLinesAndPoints()
        dpg.get_item_user_data(sender)['act_tab'] = app_data
        dpg.get_item_user_data(sender)['act_plot'] = dpg.get_item_children(app_data)[1][0]

    def deleteClosedTab(self):
        for tab in dpg.get_item_children(self.tab_bar)[1]:
            if not dpg.get_item_configuration(tab)['show']:
                # Stop playback before delete
                if tab == dpg.get_item_user_data(self.tab_bar)['act_tab']:
                    self.__timeline.stop()
                # Remove vlines and xypoints from lists before delete tab
                for figure in dpg.get_item_children(dpg.get_item_children(tab)[1][0])[1]:
                    if self.vlines is not None:
                        self.vlines = [
                            vline
                            for vline in self.vlines
                            if vline not in dpg.get_item_children(dpg.get_item_children(figure)[1][1])[1]
                        ]
                    if self.xypoints is not None:
                        self.xypoints = [
                            xypoint
                            for xypoint in self.xypoints
                            if xypoint not in dpg.get_item_children(dpg.get_item_children(figure)[1][1])[1]
                        ]
                # Delete tab
                dpg.delete_item(tab)

    # -----------------------------------------
    # File Import
    # -----------------------------------------

    def selectDataFiles(self, sender, app_data, user_data):
        print("Sender: ", sender)
        print("App Data: ", app_data)
        for key, value in app_data["selections"].items():
            self.bag_files.append(value)
            self.bag_files_name.append(key)
            database = self.getTopic(value, self.topics)
            self.msg_data_pool.append(database)
            self.createDataList(label=key, parent=self.data_pool_window, database=database)
            self.initTimeline()

    def createDataList(self, label, parent, database):
        with dpg.tree_node(label=label, parent=parent):

            def _update_count(sender, app_data, user_data):
                if app_data:
                    dpg.get_item_user_data(self.data_pool_window).append(sender)
                else:
                    dpg.get_item_user_data(self.data_pool_window).remove(sender)
                print(dpg.get_item_user_data(self.data_pool_window))

            items = list()
            for topic in database.keys():
                for entity in database[topic].keys():
                    if entity == "timestamp" or isinstance(database[topic][entity][0], str):
                        continue

                    items.append(
                        dpg.add_selectable(
                            label=entity, payload_type="plotting", callback=_update_count,
                            drag_callback=self.dragTopicPayloadCb,
                            user_data=(
                                database[topic]["timestamp"],
                                database[topic][entity],
                                entity, topic, label
                            )
                        )
                    )

                    with dpg.drag_payload(parent=dpg.last_item(),
                                          drag_data=dpg.get_item_user_data(self.data_pool_window),
                                          payload_type="plotting"):
                        dpg.add_text("drag series to plot")

    # -----------------------------------------
    # Main Entry
    # -----------------------------------------

    def specialPlotKeyEventCb(self, sender, data):
        """
        Key event callback for special plot

        Get event type with: `event_type = dpg.get_item_info(sender)["type"]`
        - "mvAppItemType::mvKeyPressHandler"
        - "mvAppItemType::mvKeyReleaseHandler"
        - "mvAppItemType::mvKeyDownHandler" (much more frequently)
        Use "mvAppItemType::mvKeyPressHandler" and

        :param sender: handler tag
        :param data: KeyPress/KeyRelease data - key, KeyDown data: [key, elapsed_time]
        """
        event_type = dpg.get_item_info(sender)["type"]
        if data == dpg.mvKey_Control:
            self.xy_plot_enabled = True if event_type == "mvAppItemType::mvKeyPressHandler" else False
        elif data == dpg.mvKey_Shift:
            self.s_length_plot_enabled = True if event_type == "mvAppItemType::mvKeyPressHandler" else False

    def run(self):
        # Call this function at the beginning in every DearPyGui application
        dpg.create_context()

        # Viewport
        dpg.create_viewport(title="DearBagPlayer", width=1500, height=900, x_pos=0, y_pos=0)

        # Icon TODO
        # dpg.set_viewport_small_icon("path/to/icon.ico")
        # dpg.set_viewport_large_icon("path/to/icon.ico")

        # Initialization
        dpg.setup_dearpygui()
        dpg.show_viewport()

        # Viewport menu bar
        with dpg.file_dialog(directory_selector=False, show=False, file_count=10,
                             width=600, height=600,
                             callback=self.selectDataFiles) as file_dialog_tag:
            dpg.add_file_extension(".*")
            dpg.add_file_extension("", color=(150, 255, 150, 255))
            dpg.add_file_extension("Source files (*.cpp *.h *.hpp){.cpp,.h,.hpp}", color=(0, 255, 255, 255))
            dpg.add_file_extension(".h", color=(255, 0, 255, 255), custom_text="[header]")
            dpg.add_file_extension(".py", color=(0, 255, 0, 255), custom_text="[Python]")
            dpg.add_file_extension(".bag", color=(0, 255, 0, 255), custom_text="[rosbag]")

        with dpg.viewport_menu_bar():
            with dpg.menu(label="Files"):
                dpg.add_menu_item(label="Import Data", callback=lambda: dpg.show_item(file_dialog_tag))

            with dpg.menu(label="Tools"):
                dpg.add_menu_item(label="Show About", callback=lambda: dpg.show_tool(dpg.mvTool_About))
                dpg.add_menu_item(label="Show Metrics", callback=lambda: dpg.show_tool(dpg.mvTool_Metrics))
                dpg.add_menu_item(label="Show Documentation", callback=lambda: dpg.show_tool(dpg.mvTool_Doc))
                dpg.add_menu_item(label="Show Debug", callback=lambda: dpg.show_tool(dpg.mvTool_Debug))
                dpg.add_menu_item(label="Show Style Editor", callback=lambda: dpg.show_tool(dpg.mvTool_Style))
                dpg.add_menu_item(label="Show Font Manager", callback=lambda: dpg.show_tool(dpg.mvTool_Font))
                dpg.add_menu_item(label="Show Item Registry", callback=lambda: dpg.show_tool(dpg.mvTool_ItemRegistry))

        # Data series list
        self.data_pool_window = dpg.add_window(label="Data Pool", height=650, width=400, user_data=list())

        # Handlers
        with dpg.handler_registry(tag="special_plot_key_event_handler"):  # show=True by default
            dpg.add_key_release_handler(key=dpg.mvKey_Control)
            dpg.add_key_press_handler(key=dpg.mvKey_Control)
            dpg.add_key_release_handler(key=dpg.mvKey_Shift)
            dpg.add_key_press_handler(key=dpg.mvKey_Shift)

        for handler in dpg.get_item_children("special_plot_key_event_handler", 1):
            dpg.set_item_callback(handler, self.specialPlotKeyEventCb)

        with dpg.item_handler_registry(tag="tab_clicked_handler"):
            dpg.add_item_clicked_handler(button=1, callback=self.tabClickedMenuCb)

        # Plot window
        with dpg.window(label="Plot Window", pos=(420, 0), height=800, width=810):
            with dpg.group(horizontal=True):
                dpg.add_button(label="Split Horizontally", callback=self.splitHorizontallyCb)
                dpg.add_button(label="Split Vertically", callback=self.splitVerticallyCb)
                dpg.add_button(label="Clear", callback=self.clearCb)

            with dpg.tab_bar(user_data={"act_tab": None, "act_plot": None, "plot_pages": 1},
                             reorderable=True, callback=self.updateActCb) as self.tab_bar:
                with dpg.tab(label=f"Plot {dpg.get_item_user_data(self.tab_bar)['plot_pages']}",
                             closable=True) as tab_tag:
                    dpg.bind_item_handler_registry(tab_tag, "tab_clicked_handler")
                    dpg.get_item_user_data(self.tab_bar)['act_tab'] = tab_tag
                    with dpg.subplots(rows=1, columns=1, no_title=True, height=600, width=800):
                        dpg.get_item_user_data(self.tab_bar)['act_plot'] = dpg.last_item()
                        self.addPlot()
                dpg.add_tab_button(label="+", tag="Add Plot Button", callback=self.addPlotPageCb, trailing=True)

            self.__timeline.createWidgets()

        # The Primary Window
        # dpg.set_primary_window("Primary Window", True)

        # Start DPG application
        # dpg.start_dearpygui()
        self.start_time = time.time()
        self.__timeline.pause()
        while dpg.is_dearpygui_running():
            # insert here any code you would like to run in the render loop
            self.update()
            # you can manually stop by using stop_dearpygui()
            dpg.render_dearpygui_frame()

        # End
        dpg.destroy_context()
