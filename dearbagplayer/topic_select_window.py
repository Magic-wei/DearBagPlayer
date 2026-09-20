import dearpygui.dearpygui as dpg


class TopicSelectWindow:
    """
    Modal window to choose which topics of a bag are imported.

    Topics that are too large (data volume or expanded entity count above the
    thresholds) are deselected by default and marked in the list, because
    importing them significantly increases import time and pollutes the
    topic/entity list.
    """

    def __init__(self, tag="topic_select_window", label="Select Topics", width=680, height=480):
        self._id = None
        self._info_text = None
        self._topic_group = None
        self._checkboxes = dict()
        self._on_import = None
        self._on_cancel = None

        with dpg.window(tag=tag, label=label, show=False, modal=True, no_close=True,
                        width=width, height=height, no_collapse=True) as self._id:
            self._info_text = dpg.add_text("")
            with dpg.child_window(height=height - 110):
                self._topic_group = dpg.add_group()
            with dpg.group(horizontal=True):
                dpg.add_button(label="Select All", callback=self._selectAllCb)
                dpg.add_button(label="Deselect All", callback=self._deselectAllCb)
                dpg.add_button(label="Import Selected", callback=self._importCb)
                dpg.add_button(label="Cancel", callback=self._cancelCb)

    @property
    def id(self):
        return self._id

    def show(self, bag_label, stats, on_import, on_cancel):
        """
        Show the topic selection window.

        :param bag_label: label of the bag being imported
        :param stats: list of RosbagParser.TopicStats, sorted by size
        :param on_import: callback(selected_topics: list)
        :param on_cancel: callback() invoked when the import is skipped
        """
        self._on_import = on_import
        self._on_cancel = on_cancel

        dpg.delete_item(self._topic_group, children_only=True)
        self._checkboxes = dict()

        large_topics = list()
        for stat in stats:
            if stat.is_large:
                large_topics.append(stat.topic)
            dpg.add_checkbox(
                label=self._formatTopic(stat),
                default_value=not stat.is_large,
                user_data=stat.topic,
                parent=self._topic_group,
            )
            self._checkboxes[stat.topic] = dpg.last_item()

        info = f"{bag_label} - {len(stats)} topic(s)"
        if large_topics:
            info += (
                f"\nWarning: {len(large_topics)} large topic(s) are deselected by default. "
                "Importing them significantly increases import time and pollutes the topic list; "
                "keeping them deselected is recommended."
            )
        dpg.set_value(self._info_text, info)

        self._center()
        dpg.configure_item(self._id, show=True)

    @staticmethod
    def _formatBytes(num_bytes):
        size = float(num_bytes)
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _formatTopic(self, stat):
        text = (f"{stat.topic}  [{stat.msgtype}]  {stat.msgcount} msgs, "
                f"~{self._formatBytes(stat.byte_size)}")
        if stat.entity_count:
            text += f", ~{stat.entity_count} entities/msg"
        if stat.is_large:
            text += "   <-- too large, do not import"
        return text

    def _center(self):
        viewport_width = dpg.get_viewport_width()
        viewport_height = dpg.get_viewport_height()
        width = dpg.get_item_width(self._id)
        height = dpg.get_item_height(self._id)
        dpg.set_item_pos(self._id, [
            max(0, int((viewport_width - width) / 2)),
            max(0, int((viewport_height - height) / 2)),
        ])

    def _selectAllCb(self):
        for checkbox in self._checkboxes.values():
            dpg.set_value(checkbox, True)

    def _deselectAllCb(self):
        for checkbox in self._checkboxes.values():
            dpg.set_value(checkbox, False)

    def _importCb(self):
        selected = [topic for topic, checkbox in self._checkboxes.items() if dpg.get_value(checkbox)]
        if not selected:
            dpg.set_value(self._info_text,
                          "Please select at least one topic, or click Cancel to skip this bag.")
            return

        dpg.configure_item(self._id, show=False)
        if self._on_import is not None:
            self._on_import(selected)

    def _cancelCb(self):
        dpg.configure_item(self._id, show=False)
        if self._on_cancel is not None:
            self._on_cancel()
