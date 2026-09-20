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

import dataclasses
import os
import sqlite3
from pathlib import Path

import numpy as np
from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore, get_types_from_msg

# Typestores used as fallback for rosbag2 files without embedded type definitions
_DEFAULT_TYPESTORES = [
    Stores.ROS2_HUMBLE,
    Stores.ROS2_FOXY,
    Stores.ROS2_GALACTIC,
    Stores.ROS2_IRON,
]

# Topic import heuristics (a future Settings dialog may make these configurable)
# A topic is considered too large if its estimated serialized data volume or
# its expanded entity count per message exceeds these thresholds.
LARGE_TOPIC_BYTES = 50 * 1024**2
LARGE_TOPIC_ENTITIES = 100000

# A header timestamp is only trusted when it is within this offset of the bag
# timestamp. Otherwise the sensor clock is considered unsynchronized (e.g.
# device uptime or GPS week time instead of Unix epoch), which would break the
# shared timeline, and the bag timestamp is used instead.
MAX_HEADER_BAG_OFFSET = 3600


@dataclasses.dataclass
class TopicStats:
    """Per-topic statistics used to decide whether a topic should be imported."""

    topic: str
    msgtype: str
    msgcount: int
    byte_size: int
    entity_count: int
    is_large: bool = False
    large_reasons: list = dataclasses.field(default_factory=list)


def getROS2TopicSizes(bag_path):
    """
    Exact per-topic data sizes from uncompressed rosbag2 sqlite files.
    Returns {topic_name: total_bytes}; empty dict when not available
    (e.g. compressed bags), in which case sizes are estimated by sampling.
    """
    sizes = dict()
    for db3_file in Path(bag_path).glob('*.db3'):
        try:
            with sqlite3.connect(db3_file) as conn:
                rows = conn.execute(
                    'SELECT topics.name, SUM(LENGTH(messages.data)) FROM messages '
                    'JOIN topics ON messages.topic_id = topics.id GROUP BY topics.id'
                )
                for name, total in rows:
                    sizes[name] = sizes.get(name, 0) + (total or 0)
        except sqlite3.Error:
            continue
    return sizes


class MissingMessageDefinitionError(ValueError):
    """
    Raised when a topic cannot be deserialized because its message
    definition is not embedded in the bag and was not loaded externally.
    """

    def __init__(self, msgtype):
        super().__init__(
            f"Missing message definition for {msgtype}. "
            "Load the corresponding .msg definitions to parse this topic."
        )
        self.msgtype = msgtype


class RosbagParser():

    def __init__(self, msg_defs_paths=None):
        self._bag_file = None
        self._msg_data = dict()
        self._msg_defs_paths = list()
        self._custom_types = dict()
        if msg_defs_paths is not None:
            self.loadMessageDefinitions(msg_defs_paths)

    @property
    def msg_defs_paths(self):
        return self._msg_defs_paths

    @property
    def bag_file(self):
        return self._bag_file

    @bag_file.setter
    def bag_file(self, file_path):
        if file_path is None:
            raise ValueError("Bag file path cannot be None")

        path = Path(file_path).expanduser()
        if not path.exists():
            raise ValueError(f"Bag path does not exist: {path}")

        if path.is_file() and path.suffix == '.bag':
            # rosbag1 file
            self._bag_file = path
        elif path.is_dir() and (path / 'metadata.yaml').exists():
            # rosbag2 directory
            self._bag_file = path
        elif path.is_file() and path.suffix == '.db3' and (path.parent / 'metadata.yaml').exists():
            # rosbag2 database file, use its directory
            self._bag_file = path.parent
        else:
            raise ValueError("File must be a .bag file, a .db3 file or a rosbag2 directory")

    @property
    def msg_data(self):
        return self._msg_data

    def loadMessageDefinitions(self, paths):
        """
        Load custom message definitions (.msg files) from the given folders or
        files. They are registered when parsing bags, which is required for
        rosbag2 files without embedded message definitions (e.g. custom
        message types recorded by vendor tools).

        Every .msg file must reside in a '<package>/msg' directory, e.g.
        'sensor_driver_msgs/msg/InsVelocity.msg' is loaded as
        'sensor_driver_msgs/msg/InsVelocity'.

        :param paths: list of folders (scanned recursively) or .msg file paths
        :return: number of loaded message definitions
        """
        msg_files = list()
        for path in paths:
            path = Path(path).expanduser()
            if path.is_file() and path.suffix == '.msg':
                msg_files.append(path)
            elif path.is_dir():
                print(f"[RosbagParser] Scanning {path} for .msg files ...", flush=True)
                msg_files.extend(self.scanMessageFiles(path))
            else:
                print(f"[RosbagParser] Message definitions path does not exist: {path}", flush=True)

        # Deduplicate types, e.g. workspace_root/src and workspace_root/install
        definitions = dict()
        for msg_file in msg_files:
            if msg_file.parent.name != 'msg':
                print(f"[RosbagParser] Skip {msg_file}: not inside a 'msg' directory", flush=True)
                continue
            msgtype = f"{msg_file.parent.parent.name}/msg/{msg_file.stem}"
            definitions.setdefault(msgtype, msg_file)

        print(f"[RosbagParser] Parsing {len(definitions)} unique message definition(s) ...", flush=True)
        loaded = 0
        for msgtype, msg_file in sorted(definitions.items()):
            try:
                self._custom_types.update(get_types_from_msg(msg_file.read_text(), msgtype))
                loaded += 1
            except Exception as e:
                print(f"[RosbagParser] Failed to parse {msg_file}: {e}", flush=True)
            if loaded % 1000 == 0 and loaded:
                print(f"[RosbagParser]   parsed {loaded}/{len(definitions)} definitions ...", flush=True)

        for path in paths:
            path = Path(path).expanduser()
            if path not in self._msg_defs_paths:
                self._msg_defs_paths.append(path)

        print(f"[RosbagParser] Loaded {loaded} custom message definition(s)", flush=True)
        return loaded

    @staticmethod
    def scanMessageFiles(root, skip_dirs=('build', '.git', '.venv', 'node_modules', '__pycache__')):
        """
        Recursively collect .msg files, skipping build/generated and hidden
        directories to keep large workspace folders fast to scan.
        """
        msg_files = list()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in skip_dirs and not d.startswith('.')
            )
            for name in sorted(filenames):
                if name.endswith('.msg'):
                    msg_files.append(Path(dirpath) / name)
        return msg_files

    def parse(self, bag_file=None, topics=None):
        """
        Parse a ROS1 (.bag) or ROS2 (rosbag2 directory / .db3) bag file
        and store message data for each topic
        """

        # Set bag file path if given
        if bag_file is not None:
            self.bag_file = bag_file

        reader = self.openReader(self._bag_file)
        try:
            # Check if topics are in the rosbag
            if topics is not None:
                if not self.hasTopics(reader, topics):
                    raise ValueError(f"At least one topic in {topics} are not present in the bag file")

            # Get all topic names
            self._msg_data = dict()
            connections = list()
            for connection in reader.connections:
                if topics is not None and connection.topic not in topics:
                    continue
                connections.append(connection)
                self._msg_data.setdefault(connection.topic, dict())

            expected = sum(connection.msgcount for connection in connections)
            print(f"[RosbagParser] Parsing {self._bag_file} ({expected} messages, "
                  f"{len(connections)} connection(s)) ...", flush=True)

            message_count = 0
            for connection, timestamp, rawdata in reader.messages(connections=connections):

                try:
                    msg = reader.deserialize(rawdata, connection.msgtype)
                except KeyError as e:
                    raise MissingMessageDefinitionError(connection.msgtype) from e

                # Full data extraction
                self.getMsgData(connection.topic, msg, upper=connection.topic)

                # Timestamp (prefer header stamp when available)
                self.addMsgData(connection.topic, "timestamp", self.getTimestamp(msg, timestamp * pow(10, -9)))

                message_count += 1
                if message_count % 10000 == 0:
                    print(f"[RosbagParser]   parsed {message_count}/{expected} messages ...", flush=True)
        finally:
            reader.close()

        # Convert all data to numpy arrays
        self.convertToNumpy()

        # Align timestamp
        self.alignTimestamp()

        print("Data loaded!", flush=True)

    def getTopicStats(self, bag_file=None,
                      large_bytes=LARGE_TOPIC_BYTES,
                      large_entities=LARGE_TOPIC_ENTITIES,
                      sample_count=2, max_scan=5000, max_scan_bytes=64 * 1024**2):
        """
        Collect statistics for all topics of a bag so the user can decide
        which topics to import before the (potentially slow) full parse.

        Byte sizes are exact for uncompressed rosbag2 files and estimated by
        sampling otherwise. Entity counts are estimated by deserializing a few
        messages per topic and counting the leaf entities they expand to.

        :return: list of TopicStats, largest first
        """
        if bag_file is not None:
            self.bag_file = bag_file

        reader = self.openReader(self._bag_file)
        try:
            stats = [
                TopicStats(topic=conn.topic, msgtype=conn.msgtype, msgcount=conn.msgcount,
                           byte_size=0, entity_count=0)
                for conn in reader.connections
            ]
            conn_index = {id(conn): index for index, conn in enumerate(reader.connections)}

            # Exact sizes for uncompressed rosbag2 recordings
            if reader.is2:
                sizes = getROS2TopicSizes(self._bag_file)
                for stat in stats:
                    stat.byte_size = sizes.get(stat.topic, 0)

            # Sample messages for entity counts (and byte sizes when unknown)
            samples = [[] for _ in stats]
            remaining = set(range(len(stats)))
            scanned = 0
            scanned_bytes = 0
            for conn, timestamp, rawdata in reader.messages():
                index = conn_index.get(id(conn))
                if index is not None and index in remaining:
                    entity_count = 0
                    try:
                        entity_count = self.countEntities(reader.deserialize(rawdata, conn.msgtype))
                    except Exception:
                        # e.g. missing message definition; stats remain usable
                        pass
                    samples[index].append((len(rawdata), entity_count))
                    if len(samples[index]) >= sample_count:
                        remaining.discard(index)
                        if not remaining:
                            break

                scanned += 1
                scanned_bytes += len(rawdata)
                if scanned >= max_scan or scanned_bytes >= max_scan_bytes:
                    break

            for stat, sampled in zip(stats, samples):
                if not sampled:
                    continue
                if stat.byte_size == 0:
                    avg_size = sum(x[0] for x in sampled) / len(sampled)
                    stat.byte_size = int(avg_size * stat.msgcount)
                stat.entity_count = max(x[1] for x in sampled)

                if stat.byte_size > large_bytes:
                    stat.large_reasons.append(f"data size ~{stat.byte_size / 1024**2:.1f} MB")
                if stat.entity_count > large_entities:
                    stat.large_reasons.append(f"~{stat.entity_count} entities per message")
                stat.is_large = bool(stat.large_reasons)
        finally:
            reader.close()

        stats.sort(key=lambda x: (x.is_large, x.byte_size), reverse=True)
        return stats

    @classmethod
    def countEntities(cls, msg):
        """
        Count the leaf entities a message expands to (mirrors getMsgData),
        used to detect topics that would flood the entity/topic list.
        """
        if cls.hasChildren(msg):
            return sum(cls.countEntities(getattr(msg, key)) for key in cls.getChildrenKeys(msg))
        if isinstance(msg, np.ndarray) and msg.dtype.kind in 'biuf':
            return len(msg)
        if isinstance(msg, (list, tuple, np.ndarray)):
            return sum(cls.countEntities(msg[k]) for k in range(len(msg)))
        return 1

    def openReader(self, bag_file):
        """
        Open a bag file with fallback typestores for rosbag2 files
        without embedded type definitions. Custom message definitions
        loaded via loadMessageDefinitions() are registered as well.
        """
        path = Path(bag_file)
        is_ros1 = path.suffix == '.bag'
        errors = list()

        # For rosbag2, always use a standard store as base when custom
        # definitions are loaded, because they may reference standard
        # message types (e.g. std_msgs/Header) not present in the bag.
        if self._custom_types and not is_ros1:
            stores = list(_DEFAULT_TYPESTORES)
        else:
            stores = [None] + list(_DEFAULT_TYPESTORES)

        for store in stores:
            try:
                typestore = get_typestore(store) if store else None
                if typestore is not None and self._custom_types:
                    typestore.register(self._custom_types)
                kwargs = {"default_typestore": typestore} if typestore else {}
                reader = AnyReader([path], **kwargs)
                reader.open()
                if self._custom_types and not is_ros1:
                    # Bags may embed definitions for some message types only,
                    # so register the custom types along with their standard
                    # dependencies.
                    reader.typestore.register(typestore.fielddefs)
                elif self._custom_types:
                    reader.typestore.register(self._custom_types)
                return reader
            except Exception as e:
                errors.append(e)

        raise RuntimeError(f"Failed to open bag file {path}: {errors[-1]}")

    @staticmethod
    def getTimestamp(msg, bag_timestamp):
        """
        Get timestamp from message header if it is available and synchronized
        with the recording, otherwise use the bag timestamp.

        Some drivers publish header stamps in a different time base (zero,
        device uptime or GPS week time). Mixing those with bag timestamps of
        other topics would break the shared timeline, so they are ignored.
        """
        header = getattr(msg, 'header', None)
        stamp = getattr(header, 'stamp', None) if header is not None else None
        if stamp is not None:
            secs = getattr(stamp, 'sec', getattr(stamp, 'secs', 0))
            nsecs = getattr(stamp, 'nanosec', getattr(stamp, 'nsecs', 0))
            header_timestamp = secs + nsecs * pow(10, -9)
            if header_timestamp > 0 and abs(header_timestamp - bag_timestamp) <= MAX_HEADER_BAG_OFFSET:
                return header_timestamp

        return bag_timestamp

    # TODO: improve speed of entities calculation
    def getMsgData(self, topic, msg, upper):
        """
        Get message data from a ROS message recursively
        """
        # alias method names to simplify code
        hasChildren = RosbagParser.hasChildren
        getChildrenKeys = RosbagParser.getChildrenKeys
        name_join = RosbagParser.name_join

        if hasChildren(msg):
            # Still has children, call getMsgData again for each field
            for key in getChildrenKeys(msg):
                self.getMsgData(topic, getattr(msg, key), name_join(upper, key))
        elif isinstance(msg, (list, tuple, np.ndarray)):
            # Fixed size arrays or sequences
            for k in range(0, len(msg)):
                self.getMsgData(topic, msg[k], name_join(upper, k))
        elif isinstance(msg, bool):
            self.addMsgData(topic, upper, int(msg))
        else:
            # int, float, str types
            self.addMsgData(topic, upper, msg)

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

    def alignTimestamp(self):
        """
        Align timestamps of all topics to the earliest timestamp
        """
        topic_timestamps = [
            self._msg_data[topic]["timestamp"]
            for topic in self._msg_data.keys()
            if len(self._msg_data[topic].get("timestamp", [])) > 0
        ]
        if not topic_timestamps:
            return

        timestamp_min = min(timestamp[0] for timestamp in topic_timestamps)
        for timestamp in topic_timestamps:
            timestamp -= timestamp_min

    @staticmethod
    def hasTopics(reader: AnyReader, topics: list):
        """
        Check whether a bag file contains certain topics.
        """
        topic_list = {connection.topic for connection in reader.connections}
        for topic in topics:
            if topic not in topic_list:
                return False

        return True

    @staticmethod
    def hasChildren(msg):
        if dataclasses.is_dataclass(msg):
            return True
        if hasattr(msg, "__slots__"):
            return True

        return False

    @staticmethod
    def getChildrenKeys(msg):
        if dataclasses.is_dataclass(msg):
            return [field.name for field in dataclasses.fields(msg) if not field.name.startswith('__')]

        return [key for key in msg.__slots__ if not str(key).startswith('__')]

    @staticmethod
    def name_join(upper, lower):
        if not upper:
            return str(lower)
        if upper[-1] == '/':
            return upper + str(lower)
        return upper + '/' + str(lower)
        # return os.path.join(ns, name)
