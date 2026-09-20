# DearBagPlayer
DearBagPlayer is a flexible rosbag player based on Dear PyGui in Python.

## Quick Start

Install dependencies:

```shell
pip install dearpygui numpy rosbags
```

Install DearBagPlayer:

```shell
pip install dearbagplayer
```

Run DearBagPlayer:

```shell
dearbagplayer
```

See [features](#Features) below to take a quick look at the main features.

Example rosbag files can be found in [Magic-wei/DearBagPlayerDemoData](https://github.com/Magic-wei/DearBagPlayerDemoData) for people who would like to try DearBagPlayer. See more details about the examples there.

This project is still under developing, see [TODO](#TODO) for future work. **Currently DearBagPlayer only supports topics that contain data entities with type of int, float, bool and lists or tuples with fixed size.**

## Dependencies

- Windows 10 or at least Ubuntu 20.04 LTS
- Python >= 3.10 - Tested on Python 3.12
- [DearPyGui](https://github.com/hoffstadt/DearPyGui)
- NumPy
- [rosbags](https://gitlab.com/ternaris/rosbags)

## Features

### Load data from rosbag files

Load up to 10 bag files each time to load data into the data pool. Both ROS1 (`.bag` files) and ROS2 (rosbag2 directories containing `metadata.yaml`) bags are supported. ROS1 bags are imported via `Files -> Import ROS1 Bag(s)`, ROS2 bags via `Files -> Import ROS2 Bag Folder`.

Before a bag is parsed, a topic selection window shows all topics with message count, estimated data size and entities per message. Topics that are too large are deselected by default with a warning, since importing them significantly increases import time and pollutes the topic list.

If a ROS2 bag does not embed message definitions, a popup will offer to import the corresponding `.msg` files via `Files -> Import Message Definitions Folder`; after loading the definitions the bag import is retried automatically. Every `.msg` file must be located in a `<package>/msg` directory.

<img src="./images/open_bags.gif" style="width:80%;" />

### Drag to plot

Select entities first and drag them to the plot area, drop to plot. Three types of plot enabled:

- Time series plot (drag and drop directly)
- XY plot (with `ctrl` key)
- Data vs. travel distance plot (with `shift` key)

<img src="./images/drag_to_plot.gif" style="width:80%;" />

### Flexible timeline modification

- Play forward/backward
- Modify play speed
- Sync timestamp by drag timeline
- Play in loop

<img src="./images/timeline.gif" style="width:80%;" />

### Zoom in/out at runtime, create new plot tab, delete and clear plots

- Zoom in/out at runtime
- Create new plot tab
- Delete single plot by right-click button of the legend
- Clear all plots in the activated plot tab with one click

<img src="./images/other_features.gif" style="width:80%;" />



## TODO

- DearBagPlayer
  - [x] Data pool:
    - [x] Get message struct from rosbag
    - [x] Get information of all the topics in a rosbag file
    - [x] Load and maintain a data dict for each topic (especially with different timestamps)
    - [x] Create selectable items for each message entity that has the type of int, float or bool
    - [x] Select bag files (up to 10 each time) to load data into the data pool
    - [x] Select dragged topic when it is not yet selected
    - [ ] Add widgets to specify topics to read from bag files (currently it has the feature of specifying topics in code)
    - [ ] Create custom series from selected topics
  - [x] Drag and drop callbacks to plot:
    - [x] Drag time series to plot
    - [x] Drag XY plot (drop with `ctrl` key)
    - [x] Drag data vs. travel distance plot (drop with `shift` key)
    - [x] Create error popup if XY plot or data vs travel distance series come from different rosbag files
  - [ ] Timeline management:
    - [x] Play forward/backward
    - [x] Modify play speed (-5 to 5)
    - [x] Sync timestamp by drag timeline
    - [x] Add button to enable/disable playing in loop
    - [ ] Add hotkeys to play/pause/stop
  - [ ] Plots:
    - [x] Create new plot tab with 2x2 subplots
    - [x] Enable drop callbacks (single time series)
    - [x] Enable drop callbacks (XY plot)
    - [x] Enable drop callbacks (Data vs. travel distance)
    - [x] Clear all plots in the activated plot tab with one click
    - [x] Create new plot tab with one click
    - [x] Enable closing plot tab
    - [x] Enable closing all series in a plot tab
    - [x] Enable renaming plot tab
    - [x] Resize at runtime
    - [x] Split plots vertically or horizontally at runtime
    - [ ] Copy plots or save to files
  - [ ] Enable live streaming
  - [ ] Enable publishing
  - [ ] Save and load config files
  - [x] Packaging
    - [x] Convert DearBagPlayer to a Python package
    - [x] Add entry point for CLI usage
    - [x] Configure setup
    - [x] Release to PyPI

## License

[MIT License](./LICENSE)
