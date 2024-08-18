"""
Copyright (c) 2021-2024, Wei Wang <wei.wang.bit@outlook.com>

RosbagParser Class

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

import numpy as np
import rosbag
import yaml
from yaml.loader import SafeLoader


class RosbagParser():

    def __init__(self):
        self._bag_file = None
        self._msg_data = dict()
    
    @property
    def bag_file(self):
        return self._bag_file
    
    @bag_file.setter
    def bag_file(self, file_path):
        if not file_path.endswith('.bag') or file_path is None:
            raise ValueError("File must be a .bag file")
        self._bag_file = file_path
    
    @property
    def msg_data(self):
        return self._msg_data
    
    def parse(self, bag_file=None, topics=None):
        """
        Parse a ROS bag file and store message data for each topic
        """

        # Set bag file path if given
        if bag_file is not None:
            self.bag_file = bag_file

        # Read bag
        bag = rosbag.Bag(self._bag_file)

        # Check if topics are in the rosbag
        if topics is not None:
            if not self.hasTopics(bag, topics):
                bag.close()
                raise ValueError(f"At least one topic in {topics} are not present in the bag file")

        # Get all topic names and msg types
        info_dict = yaml.load(bag._get_yaml_info(), Loader=SafeLoader)
        self._msg_data = dict()
        for topic_info in info_dict["topics"]:
            topic = topic_info["topic"]
            if topics is not None:
                if topic in topics:
                    self._msg_data[topic] = dict()
            else:
                self._msg_data[topic] = dict()

        for topic, msg, t in bag.read_messages(topics=topics):

            # Full data extraction
            self.getMsgData(topic, msg, upper=topic)

            # Timestamp
            timestamp = t.secs + t.nsecs * pow(10, -9)
            if 'std_msgs/Header' in msg._get_types():
                timestamp = msg.header.stamp.secs + msg.header.stamp.nsecs * pow(10, -9)
            self.addMsgData(topic, "timestamp", timestamp)

        # Convert all data to numpy arrays
        self.convertToNumpy()

        # Align timestamp
        timestamp_min = np.inf
        for topic in self._msg_data.keys():
            timestamp_min = min(timestamp_min, self._msg_data[topic]["timestamp"][0])

        for topic in self._msg_data.keys():
            self._msg_data[topic]["timestamp"] -= timestamp_min

        # Close bag
        bag.close()
        print("Data loaded!")

    # TODO: improve speed of entities calculation
    def getMsgData(self, topic, msg, upper):
        """
        Get message data from a ROS message recursively
        """
        # alias method names to simplify code
        hasChildren = RosbagParser.hasChildren
        name_join = RosbagParser.name_join

        # Check if reach end node for each recursion
        base_slots = dict().fromkeys(msg.__slots__) if hasChildren(msg) else msg

        if base_slots is msg:
            # Reach end node
            if isinstance(msg, list) or isinstance(msg, tuple):
                length = len(msg)
                base_slots = dict()
                for k in range(0, length):
                    base_slots[k] = msg[k]

                entities = list(base_slots.keys())
                for k in range(0, length):
                    entities[k] = name_join(upper, k)
                    self.addMsgData(topic, entities[k], msg[k])
            elif isinstance(msg, bool):
                self.addMsgData(topic, upper, int(msg))
            else:
                # int, float, str types
                self.addMsgData(topic, upper, msg)
        else:
            # Still has children, base_slots is dict, call getMsgData again
            for key in base_slots.keys():
                sub_msg = getattr(msg, key)
                self.getMsgData(topic, sub_msg, name_join(upper, key))

    def addMsgData(self, topic, key, data):
        if key in self._msg_data[topic].keys():
            self._msg_data[topic][key].append(data)
        else:
            self._msg_data[topic][key] = [data]

    def convertToNumpy(self):
        """
        Convert all the lists to numpy arrays for easier access
        """
        for topic in self._msg_data.keys():
            for key, data in self._msg_data[topic].items():
                self._msg_data[topic][key] = np.array(data)

    @staticmethod
    def hasTopics(bag: rosbag.Bag, topics: list[str]):
        """
        Check whether a bag file contains certain topics.
        """
        info = bag.get_type_and_topic_info()
        topic_list = list(info[1].keys())
        for topic in topics:
            if topic not in topic_list:
                return False

        return True

    @staticmethod
    def hasChildren(msg):
        if hasattr(msg, "__slots__"):
            # print(f"[hasChildren] {msg} still has children!")
            return True

        # print(f"[hasChildren] {msg} found built-in type in [int, float, bool, str, list, tuple], End!")
        return False

    @staticmethod
    def name_join(upper, lower):
        if not upper:
            return str(lower)
        if upper[-1] == '/':
            return upper + str(lower)
        return upper + '/' + str(lower)
        # return os.path.join(ns, name)
