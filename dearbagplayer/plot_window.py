import dearpygui.dearpygui as dpg
import os
import bisect
import numpy as np


class PlotWindow:

    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls, *args, **kwargs)
        return cls.instance

    def __init__(self, width=100, tag="plot_window", label="Plot Window", 
                 payload_type="plotting", timeline=None, data_pool_instance=None):
        if dpg.does_item_exist(tag):
            print(f"Tag {tag} already exists!")
            return

        # custom payload type for drag & drop
        self.payload_type = payload_type

        # special plotting types
        self.xy_plot_enabled = False
        self.s_length_plot_enabled = False

        # timeline plotting
        self.vlines = None
        self.xypoints = None

        # to be initialized later
        self._id = None
        self._tab_bar = None
        self._timeline = None
        self._data_pool_instance = None

        # init
        self.initHandlers()
        self._stage = dpg.add_stage()
        self.initWindow(label=label, tag=tag, width=width)  # update _id and _tab_bar here

        # set up additional instances
        self.addTimeline(timeline)  # update _timeline here if provided
        self.addDataPoolInstance(data_pool_instance)  # update _data_pool_instance here if provided

    @property
    def tag(self):
        return self._id

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def stage(self):
        return self._stage

    @property
    def tab_bar(self):
        return self._tab_bar
    
    @tab_bar.setter
    def tab_bar(self, value):
        self._tab_bar = value

    @property
    def timeline(self):
        return self._timeline
    
    @timeline.setter
    def timeline(self, value):
        self._timeline = value

    @property
    def data_pool_instance(self):
        return self._data_pool_instance
    
    @data_pool_instance.setter
    def data_pool_instance(self, value):
        self._data_pool_instance = value

    def submit(self, parent):
        """
        Can only submit once
        """
        if len(dpg.get_item_children(self.stage)[1]) == 0:
            raise Exception("[DataPoolWindow] Cannot submit without children!")
        dpg.push_container_stack(parent)
        dpg.unstage(self.stage)
        dpg.pop_container_stack()
        dpg.delete_item(self.stage, children_only=True)

    def setWidth(self, width):
        dpg.set_item_width(self._id, width)

    # -----------------------------------------
    # Init
    # -----------------------------------------

    def initHandlers(self):
        # plot tab handler
        with dpg.item_handler_registry(tag="tab_clicked_handler"):
            dpg.add_item_clicked_handler(button=1, callback=self.tabClickedMenuCb)
        
        # drag & drop handlers for plot (global handlers)
        with dpg.handler_registry(tag="special_plot_key_event_handler"):  # show=True by default
            dpg.add_key_release_handler(key=dpg.mvKey_Control)
            dpg.add_key_press_handler(key=dpg.mvKey_Control)
            dpg.add_key_release_handler(key=dpg.mvKey_Shift)
            dpg.add_key_press_handler(key=dpg.mvKey_Shift)

        for handler in dpg.get_item_children("special_plot_key_event_handler", 1):
            dpg.set_item_callback(handler, self.specialPlotKeyEventCb)

        ## timeline play handler (global handlers)
        with dpg.handler_registry(tag="play_event_handler"):
            dpg.add_key_release_handler(key=dpg.mvKey_Spacebar)

        for handler in dpg.get_item_children("play_event_handler", 1):
            dpg.set_item_callback(handler, self.playEventCb)

    def initWindow(self, label="Plot Window", tag="plot_window", width=100):
        with dpg.child_window(label=label, 
                              tag=tag,
                              width=width,
                              parent=self.stage,
                              ) as self.id:
            with dpg.group(horizontal=True, tag="plot_buttons"):
                dpg.add_button(label="Split Horizontally", callback=self.splitHorizontallyCb)
                dpg.add_button(label="Split Vertically", callback=self.splitVerticallyCb)
                dpg.add_button(label="Remove Horizontally", callback=self.removeHorizontallyCb)
                dpg.add_button(label="Remove Vertically", callback=self.removeVerticallyCb)
                dpg.add_button(label="Clear", callback=self.clearCb)

            with dpg.tab_bar(user_data={"act_tab": None, "act_plot": None, "plot_pages": 1},
                                reorderable=True, callback=self.updateActCb) as self.tab_bar:
                with dpg.tab(label=f"Plot {dpg.get_item_user_data(self.tab_bar)['plot_pages']}",
                                closable=True) as tab_tag:
                    dpg.bind_item_handler_registry(tab_tag, "tab_clicked_handler")
                    dpg.get_item_user_data(self.tab_bar)['act_tab'] = tab_tag
                    dpg.add_subplots(rows=1, columns=1, no_title=True)
                    dpg.get_item_user_data(self.tab_bar)['act_plot'] = dpg.last_item()
                    self.addPlotToParent(dpg.last_item())
                dpg.add_tab_button(label="+", tag="Add Plot Button", callback=self.addPlotPageCb, trailing=True)

    def addTimeline(self, timeline):
        if timeline:
            timeline.submit(self.id)
            self.timeline = timeline

    def addDataPoolInstance(self, data_pool_instance):
        if data_pool_instance:
            self.data_pool_instance = data_pool_instance

    # -----------------------------------------
    # Update
    # -----------------------------------------

    def update(self, msg_data_pool, bag_files_name):
        self.curPointUpdate(msg_data_pool, bag_files_name)
        self.checkLastPlotTab()

    def curPointUpdate(self, msg_data_pool, bag_files_name):
        """
        TODO: Consider multiple timelines for multiple topics
        """
        if self.timeline.is_played or self.timeline.is_stopped:
            if len(msg_data_pool) == 0:
                return
            self.vlinesTimeUpdate(self.timeline.now())
            self.xypointsUpdate(msg_data_pool, bag_files_name)
            if self.timeline.is_stopped:
                self.timeline.resetIsStopped()

    def vlinesTimeUpdate(self, timestamp):
        if not self.vlines:
            self.createTimeLines()
            return

        for vline in self.vlines:
            # TODO: Figure out why built-in float type get errors
            dpg.set_value(vline, [np.float64(timestamp)])

    def xypointsUpdate(self, msg_data_pool, bag_files_name):
        if not self.xypoints:
            self.createTimePoints()
            return

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
            bag_index = bag_files_name.index(bag_name)
            index = self.getIndex(msg_data_pool[bag_index][topic]["timestamp"], self.timeline.now())
            # timestamp = msg_data_pool[0][topic]["timestamp"][index]
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
        if not dpg.does_item_exist(dpg.get_item_user_data(self.tab_bar)['act_plot']):
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
        if not dpg.does_item_exist(dpg.get_item_user_data(self.tab_bar)['act_plot']):
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

    def createErrorPopup(self, error_text, popup_width=300, popup_height=60, min_size=(150, 30)):
        viewport_pos = dpg.get_viewport_pos()
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        popup_pos = [
            int(viewport_pos[0] + viewport_width // 2 - popup_width // 2),
            int(viewport_pos[1] + viewport_height // 2 - popup_height // 2),
        ]
        with dpg.mutex():
            with dpg.window(pos=popup_pos, modal=True, no_close=True, no_move=False,
                            no_title_bar=True, no_background=False, no_resize=True,
                            no_scrollbar=True, width=popup_width, height=popup_height,
                            min_size=min_size) as value_error_popup:
                dpg.add_text(error_text)
                dpg.add_button(label="OK", callback=lambda: dpg.delete_item(value_error_popup))

    def commonDropCallback(self, yaxis, app_data):

        if self.xy_plot_enabled:
            # X-Y plot with two time series

            datax = dpg.get_item_user_data(app_data[0])
            datay = dpg.get_item_user_data(app_data[1])

            # Check they belongs to the same topic and bag
            if datax[3] != datay[3] or datax[4] != datay[4]:
                self.createErrorPopup(
                    "XY plot must comes from the same bag and topic!",
                    popup_width=350, popup_height=60
                )
                return

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
                self.createErrorPopup(
                    "Data vs. s plot must come from the same bag and topic!",
                    popup_width=400, popup_height=60
                )
                return

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
        self.data_pool_instance.resetUserData()
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
        series_list = dpg.get_item_children(plot, 1)
        for series in series_list:
            if (self.vlines is None or series not in self.vlines) and \
               (self.xypoints is None or series not in self.xypoints):
                dpg.delete_item(series)

    def plotDropCallback(self, sender, app_data, user_data):
        yaxis = dpg.get_item_info(sender)["children"][1][1]
        self.commonDropCallback(yaxis, app_data)

    def axisDropCallback(self, sender, app_data, user_data):
        self.commonDropCallback(sender, app_data)

    def addPlotToParent(self, parent, title="", x_label="", y_label="", height=200, width=300,
                    equal_aspects=False, drop_plot_enabled=True):

        if drop_plot_enabled:
            plot_drop_callback = self.plotDropCallback
            axis_drop_callback = self.axisDropCallback
        else:
            plot_drop_callback = None
            axis_drop_callback = None

        plot_tag = dpg.add_plot(
            label=title, height=height, width=width, equal_aspects=equal_aspects, payload_type=self.payload_type,
            drop_callback=plot_drop_callback, parent=parent,
        )
        dpg.add_plot_legend(parent=plot_tag)
        dpg.add_plot_axis(dpg.mvXAxis, label=x_label, parent=plot_tag)
        dpg.add_plot_axis(dpg.mvYAxis, label=y_label, payload_type=self.payload_type,
                          parent=plot_tag, drop_callback=axis_drop_callback)

        return plot_tag

    def createSubplots(self, rows=1, columns=1):
        dpg.add_subplots(rows=rows, columns=columns, no_title=True, height=600, width=800, no_resize=False)
        self.addPlotToParent(dpg.last_item())

    # -----------------------------------------
    # Plot Canvas Control
    # -----------------------------------------

    def addPlotPageCb(self, sender, app_data, user_data):
        dpg.get_item_user_data(self.tab_bar)['plot_pages'] += 1
        with dpg.tab(label=f"Plot {dpg.get_item_user_data(self.tab_bar)['plot_pages']}",
                     parent=self.tab_bar, closable=True) as tab_tag:
            dpg.bind_item_handler_registry(tab_tag, "tab_clicked_handler")
            self.createSubplots()

    def tabClickedMenuCb(self, sender, app_data, user_data):
        """
        Right-clicked Event Window for Plot Tabs

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
            plot_tag = self.addPlotToParent(subplots)
            plots.insert(cols * (rows - row), plot_tag)
        dpg.reorder_items(subplots, 1, plots)
        dpg.configure_item(subplots, columns=cols + 1)

    def splitVerticallyCb(self, sender, app_data, user_data):
        subplots = dpg.get_item_user_data(self.tab_bar)['act_plot']
        cols = dpg.get_item_configuration(subplots)['cols']
        rows = dpg.get_item_configuration(subplots)['rows']
        for col in range(cols):
            self.addPlotToParent(subplots)
        dpg.configure_item(subplots, rows=rows + 1)

    def removeHorizontallyCb(self, sender, app_data, user_data):
        subplots = dpg.get_item_user_data(self.tab_bar)['act_plot']
        cols = dpg.get_item_configuration(subplots)['cols']
        rows = dpg.get_item_configuration(subplots)['rows']
        if cols <= 1:
            return
        plots = dpg.get_item_children(subplots)[1]
        for row in range(rows):
            plot_tag = plots[cols * (rows - row) - 1]
            dpg.delete_item(plot_tag)
        dpg.reorder_items(subplots, 1, plots)
        dpg.configure_item(subplots, columns=cols - 1)

    def removeVerticallyCb(self, sender, app_data, user_data):
        subplots = dpg.get_item_user_data(self.tab_bar)['act_plot']
        cols = dpg.get_item_configuration(subplots)['cols']
        rows = dpg.get_item_configuration(subplots)['rows']
        if rows <= 1:
            return
        plots = dpg.get_item_children(subplots)[1]
        for col in range(cols):
            plot_tag = plots[cols * (rows - 1) + col]
            dpg.delete_item(plot_tag)
        dpg.configure_item(subplots, rows=rows - 1)

    def clearCb(self, sender, app_data, user_data):
        self.timeline.stop()
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
        self.resizeActPlot()

    def deleteClosedTab(self):
        for tab in dpg.get_item_children(self.tab_bar)[1]:
            if not dpg.get_item_configuration(tab)['show']:
                # Stop playback before delete
                if tab == dpg.get_item_user_data(self.tab_bar)['act_tab']:
                    self.timeline.stop()
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
    # Layout
    # -----------------------------------------

    def resizeActPlot(self):
        width = dpg.get_item_width(self.id) - 15
        height = dpg.get_item_height(self.id) - 150
        plot_tag = dpg.get_item_user_data(self.tab_bar)['act_plot']
        dpg.configure_item(plot_tag, width=width, height=height)

    # -----------------------------------------
    # Global Handlers
    # -----------------------------------------

    def specialPlotKeyEventCb(self, sender, data):
        """
        Key event callback for special plot

        Get event type with: `event_type = dpg.get_item_info(sender)["type"]`
        - "mvAppItemType::mvKeyPressHandler"
        - "mvAppItemType::mvKeyReleaseHandler"
        - "mvAppItemType::mvKeyDownHandler" (much more frequently)

        :param sender: handler tag
        :param data: KeyPress/KeyRelease data - key, KeyDown data: [key, elapsed_time]
        """
        event_type = dpg.get_item_info(sender)["type"]
        if data == dpg.mvKey_Control:
            self.xy_plot_enabled = True if event_type == "mvAppItemType::mvKeyPressHandler" else False
        elif data == dpg.mvKey_Shift:
            self.s_length_plot_enabled = True if event_type == "mvAppItemType::mvKeyPressHandler" else False

    def playEventCb(self, sender, data):
        """
        Play/Pause timeline when released

        :param sender: handler tag
        :param data: KeyPress/KeyRelease data - key, KeyDown data: [key, elapsed_time]
        """
        if self.timeline.is_played:
            self.timeline.pause()
        else:
            self.timeline.play()
