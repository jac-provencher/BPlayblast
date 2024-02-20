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

    DEFAULT_PADDING = 4

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
        "Image": ["jpg", "png", "tif"]
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
        self.set_h264_settings(BPlayblast.DEFAULT_H264_QUALITY, BPlayblast.DEFAULT_H264_PRESET)
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

        self._resolution_preset = None

        try:
            width_height = self.preset_to_resolution(resolution)
            self._resolution_preset = resolution
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
        
        self._width_height = (width_height[0], width_height[1])

    def get_resolution_width_height(self):
        if self._resolution_preset:
            return self.preset_to_resolution(self._resolution_preset)
        
        return self._width_height

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
        
        return (start_frame, end_frame)
    
    def set_encoding(self, container_format, encoder):
        if container_format not in (containers := BPlayblast.VIDEO_ENCODER_LOOKUP.keys()):
            self.log_error(f"Invalid container: {container_format}. Expected one of {containers}")
        
        if encoder not in (encoders := BPlayblast.VIDEO_ENCODER_LOOKUP[container_format]):
            self.log_error(f"Invalid encoder: {encoder}. Expected one of {encoders}")

        self._container_format = container_format
        self._encoder = encoder

    def set_h264_settings(self, quality, preset):
        if not quality in (h264_qualities := BPlayblast.H264_QUALITIES.keys()):
            self.log_error(f"Invalid h264 quality: {quality}. Expected of {h264_qualities}")
            return
        
        if preset not in (h264_presets := BPlayblast.H264_PRESETS):
            self.log_error(f"Invalid h264 preset: {preset}. Expected of {h264_presets}")
            return
        
        self._h264_quality = quality
        self._h264_preset = preset

    def get_h264_settings(self):
        return {
            "quality": self._h264_quality,
            "preset": self._h264_preset
        }

    def set_image_settings(self, quality):
        if 0 < quality <= 100:
            self._image_quality = quality
        else:
            self.log_error(f"Invalid image quality: {quality}. Expected value betwenn 1-100")

    def get_image_settings(self):
        return {
            "quality": self._image_quality
        }
 
    def set_frame_range(self, frame_range):
        resolve_frame_range = self.resolve_frame_range(frame_range)
        if not resolve_frame_range:
            return
        
        self._frame_range_preset = None
        if frame_range in BPlayblast.FRAME_RANGE_PRESETS:
            self._frame_range_preset = frame_range
        
        self._start_frame = resolve_frame_range[0]
        self._end_frame = resolve_frame_range[1]

    def get_start_end_frame(self):
        if self._frame_range_preset:
            return self.preset_to_frame_range(self._frame_range_preset)
        
        return (self._start_frame, self._end_frame)

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
        
    def requires_ffmpeg(self):
        return self._container_format != "Image"

    def execute(self, output_dir, filename, padding=4, show_ornaments=True, show_in_viewer=True, overwrite=False):

        if self.requires_ffmpeg() and not self.validate_ffmpeg():
            self.log_error("ffmpeg executable is not configured. See script editor for details.")
            return
        
        viewport_model_panel = self.get_viewport_panel()
        if not viewport_model_panel:
            self.log_error("An active viewport is not selected. Select the viewport and retry")
            return

        if not output_dir:
            self.log_error("Output directory path not set")
            return
        if not filename:
            self.log_error("Output file name not set")
            return

        output_dir = self.resolve_output_directory_path(output_dir)
        filename = self.resolve_output_filename(filename)
        
        if padding <= 0:
            padding = BPlayblast.DEFAULT_PADDING

        if self.requires_ffmpeg():
            output_path = os.path.normpath(os.path.join(output_dir, f"{filename}.{self._container_format}"))
            if not overwrite and os.path.exists(output_path):
                self.log_error(f"Output file already exists. Enable overwrite to ignore.")
                return

            playblast_output_dir = f"{output_dir}/playblast_temp"
            playblast_output = os.path.normpath(os.path.join(playblast_output_dir, filename))
            force_overwrite = True
            compression = "png"
            image_quality = 100
            index_from_zero = True
            viewer = False

        else:
            playblast_output = os.path.normpath(os.path.join(output_dir, filename))
            force_overwrite = overwrite
            compression = self._encoder
            image_quality = self._image_quality
            index_from_zero = False
            viewer = show_in_viewer 

        width_height = self.get_resolution_width_height()
        start_frame, end_frame = self.get_start_end_frame()
        
        options = {
            "filename": playblast_output,
            "widthHeight": width_height,
            "percent": 100,
            "startTime": start_frame,
            "endTime": end_frame,
            "clearCache": True,
            "forceOverwrite": force_overwrite,
            "format": "image",
            "compression": compression,
            "quality": image_quality,
            "indexFromZero": index_from_zero,
            "framePadding": padding,
            "showOrnaments": show_ornaments,
            "viewer": viewer
        }

        self.log_output(f"Playblast options: {options}")

        # Store original viewport settings
        orig_camera = self.get_active_camera()

        camera = self._camera
        if not camera:
            camera = orig_camera

        if not camera in cmds.listCameras():
            self.log_error(f"Camera does not exists: {camera}")
            return
        
        self.set_active_camera(camera)

        playblast_failed = False
        try:
            cmds.playblast(**options)
        except:
            traceback.print_exc()
            self.log_error("Failed to created playblast. See script editor for details")
            playblast_failed = True
        finally:
            # Restore original viewport settings
            self.set_active_camera(orig_camera)

        if playblast_failed:
            return


if __name__ == "__main__":

    playblast = BPlayblast()
    playblast.set_camera("top")
    playblast.set_encoding("Image", "jpg")
    playblast.execute("E:/BASA", "output")

