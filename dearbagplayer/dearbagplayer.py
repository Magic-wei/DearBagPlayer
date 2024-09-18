"""
Copyright (c) 2021-2024, Wei Wang <wei.wang.bit@outlook.com>

DearBagPlayer Application
"""


try:
    from .timeline_widgets import TimelineWidgets
    from .rosbag_parser import RosbagParser
    from .data_pool_window import DataPoolWindow
    from .plot_window import PlotWindow
    from .config import Config
    from . import __version__
except ImportError as e:
    raise ImportError(f"{str(e)}")

import dearpygui.dearpygui as dpg
import time


class DearBagPlayer:

    def __init__(self, topics=None):

        # Call this function at the beginning in every DearPyGui application
        dpg.create_context()

        # Bag info
        self.bag_files = list()
        self.bag_files_name = list()

        # Data
        self.data_pool_window = DataPoolWindow()
        self.topics = topics # TODO: self.topics is never used, and should updated at runtime
        self.msg_data_pool = list()
        self.rosbag_parser = RosbagParser()

        # Timeline
        self.min_time = 0.0
        self.max_time = 0.0
        self.__timeline = TimelineWidgets(start_time=0.0, duration=0.0, loop_enabled=True)

        # Time series control
        self.start_time = 0.0
        self.__index = 0
        self.__head = 0.0

        # Plots
        self.plot_window = PlotWindow()
        self.plot_window.addTimeline(self.__timeline)
        self.plot_window.addDataPoolInstance(self.data_pool_window)

        # Series selector
        self.tab_bar = self.plot_window.tab_bar

        # Resize
        self.main_window_size = [-1, -1]
        self.scale = [0.3, 0.7]
        self.plot_window_min_width = -1
        self.data_pool_min_width = -1

        # UI design
        self.config = Config(verbose=True)
        self.delta_width_vp = self.config.delta_width_vp  # viewport width - non-primary window width
        self.delta_height_vp = self.config.delta_height_vp  # viewport height - non-primary window height
        self.delta_height_child = self.config.delta_height_child  # non-primary window height - child height
        self.vertical_separator_width = self.config.vertical_separator_width

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

    def parseBagFile(self, bag_file, topics):
        """
        Parse a rosbag file and return the msg data as dictionary
        """
        try:
            self.rosbag_parser.parse(bag_file, topics)
            return self.rosbag_parser.msg_data
        except Exception as e:
            error_message = f"RosbagParser Error: {str(e)}"
            print(error_message)
            # TODO: old popup code not working anymore
            self.createErrorPopup(
                error_message,
                popup_width=350, popup_height=60
            )
            return None

    # -----------------------------------------
    # Update
    # -----------------------------------------

    def update(self):
        self.timelineUpdate()
        self.plot_window.update(self.msg_data_pool, self.bag_files_name)

    def timelineUpdate(self):
        # Update head, index, and rendering
        if self.__timeline.head_updated:
            # Manually set head
            self.__timeline.resetHeadUpdated()

        delta_time = dpg.get_delta_time()
        self.__timeline.render(delta_time)
        self.__head = self.__timeline.now()
  
    # -----------------------------------------
    # Layout
    # -----------------------------------------

    def resizeChildWindows(self):
        self.main_window_size[0] = dpg.get_item_width("main_window")
        self.main_window_size[1] = dpg.get_item_height("main_window")
        dpg.configure_item(
            self.data_pool_window.id,
            width=int(self.scale[0] * self.main_window_size[0]),
            height=int(self.main_window_size[1] - self.delta_height_child),
        )
        dpg.configure_item(
            self.plot_window.id,
            width=int(self.scale[1] * self.main_window_size[0] - self.vertical_separator_width - 20),
            height=int(self.main_window_size[1] - self.delta_height_child),
        )
        self.plot_window.resizeActPlot()

    def resizeMainWindowCb(self):
        self.resizeChildWindows()
        delta_x = dpg.get_item_pos("main_window")[0]
        dpg.set_viewport_width(self.main_window_size[0] + self.delta_width_vp - delta_x)
        dpg.set_viewport_height(self.main_window_size[1] + self.delta_height_vp)
        dpg.set_viewport_pos([dpg.get_viewport_pos()[0] + delta_x, dpg.get_viewport_pos()[1]])

    def resizeViewportCb(self):
        dpg.configure_item("main_window",
                           width=dpg.get_viewport_width() - self.delta_width_vp,
                           height=dpg.get_viewport_height() - self.delta_height_vp)
        self.resizeChildWindows()

    def addVerticalSeparator(self, parent):
        """TODO: Fix init min width settings"""
        separator = dpg.add_button(width=3, height=-1, parent=parent)

        def clickedCb():
            while dpg.is_mouse_button_down(0):
                # Calculate new widths
                x_pos = dpg.get_mouse_pos(local=False)[0]
                dpg.split_frame(delay=10)
                x_delta = dpg.get_mouse_pos(local=False)[0] - x_pos
                width_left = dpg.get_item_width(self.data_pool_window.id) + x_delta
                width_right = dpg.get_item_width(self.plot_window.id) - x_delta

                # Update min widths
                self.data_pool_min_width = 300
                self.plot_window_min_width = max(
                    dpg.get_item_rect_size(self.__timeline.widget_group)[0] + 100,
                    dpg.get_item_rect_size("plot_buttons")[0] + 100,
                )

                # Limit new widths
                if width_right < self.plot_window_min_width:
                    width_right = self.plot_window_min_width
                    width_left = self.main_window_size[0] - width_right
                if width_left < self.data_pool_min_width:
                    width_left = self.data_pool_min_width
                    width_right = self.main_window_size[0] - width_left

                # Update scale and call resize callback
                self.scale[0] = width_left / self.main_window_size[0]
                self.scale[1] = 1 - self.scale[0]
                self.resizeMainWindowCb()

        with dpg.item_handler_registry() as item_handler:
            dpg.add_item_clicked_handler(callback=clickedCb)
        dpg.bind_item_handler_registry(item=separator, handler_registry=item_handler)

        return separator

    # -----------------------------------------
    # File Import
    # -----------------------------------------

    def selectDataFilesCb(self, sender, app_data, user_data):
        """
        :param sender: file_dialog tag
        :param app_data:
            {'file_path_name': ...,
             'file_name': ...,
             'current_path': ...,
             'current_filter': ...,
             'min_size': ..., 'max_size': ...,
             'selections': {'<file_name>': '<file_path>', ...},
             }
        :param user_data: None
        """
        for key, bagfile in app_data["selections"].items():
            self.bag_files.append(bagfile)
            self.bag_files_name.append(key)
            database = self.parseBagFile(bagfile, self.topics)
            if database is None:
                continue
            self.msg_data_pool.append(database)
            self.data_pool_window.addNewEntries(label=key, database=database)
        self.initTimeline()

    # -----------------------------------------
    # Main Entry
    # -----------------------------------------

    def run(self):

        # file importer widget
        with dpg.file_dialog(directory_selector=False, show=False, file_count=10,
                        width=600, height=400, modal=True,
                        callback=self.selectDataFilesCb) as file_dialog_tag:
            dpg.add_file_extension(".bag", color=(0, 255, 0, 255), custom_text="[rosbag]")
            dpg.add_file_extension(".*")

        # Icon TODO
        # dpg.set_viewport_small_icon("path/to/icon.ico")
        # dpg.set_viewport_large_icon("path/to/icon.ico")

        # Viewport
        dpg.create_viewport(title=f"DearBagPlayer - {__version__}", resizable=self.config.enable_vp_resize,
                            width=800, height=600, x_pos=0, y_pos=0,
                            min_width=800, min_height=600)

        # Viewport menu bar
        with dpg.viewport_menu_bar(tag="menubar"):
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

        self.delta_height_vp += dpg.get_item_height("menubar")  # add menubar height

        # Primary Window
        dpg.add_window(tag="main_window",
                       no_scrollbar=True,
                       no_title_bar=True,
                       no_move=True,
                       min_size=[dpg.get_viewport_min_width(), dpg.get_viewport_min_height()],
                       pos=[0, dpg.get_item_height("menubar")],
                       width=dpg.get_viewport_width() - self.delta_width_vp,
                       height=dpg.get_viewport_height() - self.delta_height_vp,
                       )

        self.main_window_size[0] = dpg.get_item_width("main_window")
        self.main_window_size[1] = dpg.get_item_height("main_window")

        # Workspace
        main_window_group = dpg.add_group(horizontal=True, parent="main_window")

        self.data_pool_window.setWidth(int(self.scale[0]*self.main_window_size[0]))
        self.data_pool_window.submit(main_window_group)

        self.addVerticalSeparator(parent=main_window_group)

        self.plot_window.setWidth(int(self.scale[1]*self.main_window_size[0]))
        self.plot_window.submit(main_window_group)

        # Bind resize handler
        if self.config.enable_vp_resize:
            dpg.set_viewport_resize_callback(callback=self.resizeViewportCb)
        else:
            with dpg.item_handler_registry(tag="resize_handler"):
                dpg.add_item_resize_handler(callback=self.resizeMainWindowCb)
            dpg.bind_item_handler_registry("main_window", "resize_handler")

        dpg.setup_dearpygui()
        dpg.show_viewport()
        self.resizeViewportCb() # fix initial viewport size issue

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
