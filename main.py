import os
import traceback
from PySide2 import QtCore
import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMaya as om


class BPlayblast(QtCore.QObject):

    VERSION = "0.0.1"

    DEFAULT_FFMPEG_PATH = "D:/programs/ffmpeg/bin/ffmpeg.exe"
    DEFAULT_CAMERA = None
    DEFAULT_RESOLUTION = "Render"
    DEFAULT_FRAME_RANGE = "Render"

    DEFAULT_CONTAINER = "mp4"
    DEFAULT_ENCODER = "h264"
    DEFAULT_H264_QUALITY = "High"
    DEFAULT_H264_PRESET = "fast"
    DEFAULT_IMAGE_QUALITY = 100

    RESOLUTION_LOOKUP = {
        "Render":(),
        "HD 1080": (1920, 1080),
        "HD 720": (1280, 720),
        "HD 540": (960, 540)
    }

    FRAME_RANGE_PRESETS = [
        "Render",
        "Playback",
        "Animation"
    ]

    VIDEO_ENCODER_LOOKUP = {
        "mov": ["h264"],
        "mp4": ["h264"],
        "image": ["jpg", "png", "tif"]
    }

    H264_QUALITIES = {
        "Very high": 18,
        "High": 20,
        "Medium": 23,
        "Low": 26
    }

    H264_PRESETS = [
        "veryslow",
        "slow",
        "medium",
        "fast",
        "faster",
        "ultrafast"
    ]

    output_logged = QtCore.Signal(str)

    def __init__(self, ffmpeg_path=None, log_to_maya=True):

        super(BPlayblast, self).__init__()

        self.set_ffmpeg_path(ffmpeg_path)
        self.set_maya_logging_enabled(log_to_maya)

        self.set_camera(BPlayblast.DEFAULT_CAMERA)
        self.set_resolution(BPlayblast.DEFAULT_RESOLUTION)
        self.set_frame_range(BPlayblast.DEFAULT_FRAME_RANGE)

        self.set_encoding(BPlayblast.DEFAULT_CONTAINER, BPlayblast.DEFAULT_ENCODER)
        self.set_h264_settings(BPlayblast.DEFAULT_IMAGE_QUALITY, BPlayblast.DEFAULT_H264_PRESET)
        self.set_image_settings(BPlayblast.DEFAULT_IMAGE_QUALITY)

    def set_maya_logging_enabled(self, enabled):
        self._log_to_maya = enabled

    def log_error(self, text):
        if self._log_to_maya:
            om.MGlobal.displayError("[BPlayblast] {0}".format(text))

        self.output_logged.emit("[ERROR] {0}".format(text))

    def log_warning(self, text):
        if self._log_to_maya:
            om.MGlobal.displayWarning("[BPlayblast] {0}".format(text))

        self.output_logged.emit("[WARNING] {0}".format(text))

    def log_output(self, text):
        if self._log_to_maya:
            om.MGlobal.displayInfo(text)

        self.output_logged.emit(text)

    def set_ffmpeg_path(self, ffmpeg_path):
        """_summary_

        Args:
            ffmpeg_path (_type_): _description_
        """
        if ffmpeg_path:
            self._ffmpeg_path = ffmpeg_path
        else:
            self._ffmpeg_path = BPlayblast.DEFAULT_FFMPEG_PATH

    def get_ffmpeg_path(self):

        return self._ffmpeg_path

    def validate_ffmpeg(self):

        if not self._ffmpeg_path:
            self.log_error("ffmpeg executable path not set")
            return False

        elif not os.path.exists(self._ffmpeg_path):
            self.log_error(f"ffmpeg executable path does not exists: {self._ffmpeg_path}")
            return False

        elif os.path.isdir(self._ffmpeg_path):
            self.log_error(f"Invalid ffmpeg path: {self._ffmpeg_path}")
            return False

        return True

    def set_resolution(self, resolution):
        try:
            width_height = self.preset_to_resolution(resolution)
        except:
            width_height = resolution

        valid_resolution = True
        try:
            if not (isinstance(width_height[0], int) and isinstance(width_height[1], int)):
                valid_resolution = False
        except:
            valid_resolution = False

        if valid_resolution:
            if width_height[0] <= 0 or width_height[1] <= 0:
                self.log_error(f"Invalid resolution: {width_height}. Values must be greater than zero.")
                return
        else:
            presets = [f"'{preset}'" for preset in BPlayblast.RESOLUTION_LOOKUP.keys()]
            self.log_error(f"Invalid resolution: {width_height}. Expected one of [int, int], {', '.join(presets)}")
            return
        
        self._width_height = width_height

    def preset_to_resolution(self, resolution_preset):
        """_summary_

        Args:
            resolution_preset (_type_): _description_

        Raises:
            RuntimeError: _description_

        Returns:
            _type_: _description_
        """
        if resolution_preset == "Render":
            width = cmds.getAttr("defaultResolution.width")
            height = cmds.getAttr("defaultResolution.height")
            return (width, height)
        elif resolution_preset in BPlayblast.RESOLUTION_LOOKUP.keys():
            return BPlayblast.RESOLUTION_LOOKUP[resolution_preset]
        else:
            raise RuntimeError(f"Invalid resolution preset: {resolution_preset}")
        
    def preset_to_frame_range(self, frame_range_preset):
        if frame_range_preset == "Render":
            start_frame = cmds.getAttr("defaultRenderGlobals.startFrame")
            end_frame = cmds.getAttr("defaultRenderGlobals.endFrame")
        elif frame_range_preset == "Playback":
            start_frame = int(cmds.playbackOptions(q=True, minTime=True))
            end_frame = int(cmds.playbackOptions(q=True, maxTime=True))            
        elif frame_range_preset == "Animation":
            start_frame = int(cmds.playbackOptions(q=True, animationStartTime=True))
            end_frame = int(cmds.playbackOptions(q=True, animationEndTime=True))
        else:
            raise RuntimeError(f"Invalid frame range preset: {frame_range_preset}")
        
        return [start_frame, end_frame]
    
    def set_encoding(self, container_format, encoder):
        if container_format not in (containers := BPlayblast.VIDEO_ENCODER_LOOKUP.keys()):
            self.log_error(f"Invalid container: {container_format}. Expected one of {containers}")
        
        if encoder not in (encoders := BPlayblast.VIDEO_ENCODER_LOOKUP[container_format]):
            self.log_error(f"Invalid encoder: {encoder}. Expected one of {encoders}")

        self._container_format = container_format
        self._encoder = encoder

    def set_h264_settings(self, quality, preset):
        pass

    def get_h264_settings(self):
        pass

    def set_image_settings(self, quality):
        pass

    def get_image_settings(self):
        pass
 
    def set_frame_range(self, frame_range):
        resolve_frame_range = self.resolve_frame_range(frame_range)
        if not resolve_frame_range:
            return
        
        self._start_frame = resolve_frame_range[0]
        self._end_frame = resolve_frame_range[1]

    def set_camera(self,  camera):  
        if camera and camera not in cmds.listCameras():
            self.log_error(f"Camera does not exist: {camera}")
            camera = None

        self._camera = camera
    
    def set_active_camera(self, camera_name):
        model_panel = self.get_viewport_panel()
        if model_panel:
            mel.eval(f"lookThroughModelPanel {camera_name} {model_panel}")
        else:
            self.log_error("Failed to set active camera. A viewport is not active.")

    def get_active_camera(self):
        model_panel = self.get_viewport_panel()
        if not model_panel:
            self.log_error("Failed to get active camera. A viewport is not active.")
            return None
        
        return cmds.modelPanel(model_panel, q=True, camera=True) # returns the camera name for a given model_panel

    def get_viewport_panel(self):
        model_panel = cmds.getPanel(withFocus=True) # dans la liste de panel, returns active view panel's name
        try:
            cmds.modelPanel(model_panel, q=True, modelEditor=True)
            return model_panel
        except:
            self.log_error("Failed to get active view")

    def get_scene_name(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        scene_name = cmds.file(q=True, sceneName=True, shortName=True)
        if scene_name:
            scene_name = os.path.splitext(scene_name)[0]
        else:
            scene_name = "untitled"

        return scene_name

    def get_project_dir_path(self):
        return cmds.workspace(q=True, rootDirectory=True)

    def resolve_output_directory_path(self, dir_path):
        """_summary_

        Args:
            dir_path (_type_): _description_

        Returns:
            _type_: _description_
        """
        if "{project}" in dir_path:
            dir_path = dir_path.replace("{project}", self.get_project_dir_path())

        return dir_path
    
    def resolve_output_filename(self, filename):

        if "{scene}" in filename:
            filename = filename.replace("{scene}", self.get_scene_name())

        return filename
    
    def resolve_frame_range(self, frame_range):
        try:
            if type(frame_range) in [list, tuple]:
                start_frame = frame_range[0]
                end_frame = frame_range[1]
            else:
                start_frame, end_frame = self.preset_to_frame_range(frame_range)

            return [start_frame, end_frame]

        except:
            presets = [f"'{preset}'" for preset in BPlayblast.FRAME_RANGE_PRESETS]
            self.log_error(f"Invalid frame range. Expected one of (start_frame, end_frame) or {', '.join(presets)}")

            return None

    def execute(self, output_dir, filename, padding=4, show_ornaments=True, show_in_viewer=True, overwrite=False):
        """This function is call when playblast button is clicked. It will executes the playblast process.

        Args:
            output_dir (str): directory where playblast content will be stored
            filename (str): playblast content name
            padding (int, optional): the amount of number in suffix for an image sequence. Defaults to 4.
            show_ornaments (bool, optional): toggle on/off to show ornaments in the view. Defaults to True.
            show_in_viewer (bool, optional): _description_. Defaults to True.
            overwrite (bool, optional): toggle on/off if user wants to overwrite existing file. Defaults to False.
        """
        if not output_dir:
            self.log_error("Output directory path not set")
            return
        if not filename:
            self.log_error("Output file name not set")
            return

        output_dir = self.resolve_output_directory_path(output_dir)
        filename = self.resolve_output_filename(filename)

        self.log_output(f"Output directory: {output_dir}")
        self.log_output(f"Output filename: {filename}")

        if self.validate_ffmpeg():
            self.log_output("TODO: execute playblast")


if __name__ == "__main__":

    playblast = BPlayblast()
    playblast.set_resolution(("allo", 20))

    print(playblast._width_height)

