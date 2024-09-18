import sys


class Config:

    # UI settings
    delta_width_vp = 0
    delta_height_vp = 0
    delta_height_child = 15
    vertical_separator_width = 15
    enable_vp_resize = True

    def __init__(self, verbose=False):
        if sys.platform.startswith('win'):
            self.delta_width_vp = 17
            self.delta_height_vp = 40
            self.enable_vp_resize = False
        elif sys.platform.startswith('linux'):
            self.delta_width_vp = 0
            self.delta_height_vp = 0
            self.enable_vp_resize = True
        else:
            pass
        if verbose:
            print(f'Use UI configurations for {sys.platform}. Viewport resize: {self.enable_vp_resize}')