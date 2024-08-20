import dearpygui.dearpygui as dpg

class DataPoolWindow:

    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls, *args, **kwargs)
        return cls.instance

    def __init__(self, width=100, tag="data_pool_window", label="Data Pool", payload_type="plotting"):
        if dpg.does_item_exist(tag):
            print("Tag 'data_pool_window' already exists!")
            return
        self._stage = dpg.add_stage()
        self._id = dpg.add_child_window(
            label=label,
            user_data=list(),
            width=width,
            tag=tag,
            parent=self._stage,
        )
        self.payload_type = payload_type
    
    @property
    def tag(self):
        return self._id

    @property
    def id(self):
        return self._id

    @property
    def stage(self):
        return self._stage

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

    def addNewEntries(self, label, database):
        """
        Add new entries to the data pool window
        """

        with dpg.tree_node(label=label, parent=self.id):

            items = list()
            for topic in database.keys():
                for entity in database[topic].keys():
                    if entity == "timestamp" or isinstance(database[topic][entity][0], str):
                        continue

                    items.append(
                        dpg.add_selectable(
                            label=entity, payload_type=self.payload_type, callback=self.selectCountCb,
                            drag_callback=self.dragTopicPayloadCb,
                            user_data=(
                                database[topic]["timestamp"],
                                database[topic][entity],
                                entity, topic, label
                            )
                        )
                    )

                    with dpg.drag_payload(parent=dpg.last_item(),
                                          drag_data=dpg.get_item_user_data(self.id),
                                          payload_type=self.payload_type):
                        dpg.add_text("drag series to plot")

    def resetUserData(self):
        length = len(dpg.get_item_user_data(self.id))
        for i in range(0, length):
            item = dpg.get_item_user_data(self.id)[length - 1 - i]
            dpg.set_value(item, False)
            dpg.get_item_user_data(self.id).remove(item)

    def selectCountCb(self, sender, app_data, user_data):
        if app_data:
            dpg.get_item_user_data(self.id).append(sender)
        else:
            dpg.get_item_user_data(self.id).remove(sender)
        print(dpg.get_item_user_data(self.id))

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