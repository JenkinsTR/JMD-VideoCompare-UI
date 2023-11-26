# This Python file uses the following encoding: utf-8
import sys
import subprocess
import re
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox, QSplashScreen
from PySide6.QtGui import QTextCursor, QDesktopServices, QFontDatabase, QPixmap
from PySide6.QtCore import Qt, QThread, Signal, QUrl
import logging

# Setup logging
logging.basicConfig(filename='app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')

# Import the UI layout
from ui_form import Ui_MainWindow

class FontScanner(QThread):
    update_signal = Signal(str)

    def __init__(self, font_dir):
        super().__init__()
        self.font_dir = font_dir
        self.font_cache = {}  # Initialize the font cache here

    def run(self):
        font_files = os.listdir(self.font_dir)
        total_fonts = len(font_files)
        for idx, file_name in enumerate(font_files):
            font_path = os.path.join(self.font_dir, file_name)
            if os.path.isfile(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)  # Add font and get font ID
                for family in QFontDatabase.applicationFontFamilies(font_id):
                    self.font_cache[family] = font_path  # Populate the font_cache
                    self.update_signal.emit(f"Scanning fonts: {idx+1}/{total_fonts} {file_name}")
        self.update_signal.emit("Font scanning complete.")

    def get_font_cache(self):
        return self.font_cache

class FFmpegThread(QThread):
    update_signal = Signal(str)

    def __init__(self, command):
        QThread.__init__(self)
        self.command = command

    def run(self):
        try:
            process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                standardized_line = line.replace('\r\n', '\n').replace('\r', '\n').strip()
                self.update_signal.emit(standardized_line)
            process.wait()
            self.update_signal.emit("Processing completed successfully.")
        except Exception as e:
            self.update_signal.emit(f"FFmpeg subprocess error: {e}")

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.logoButton.clicked.connect(self.open_url)

        # Connect buttons
        self.ui.pushButton.clicked.connect(self.process_videos)
        self.ui.pushButtonVideo1Browse.clicked.connect(self.browse_video1)
        self.ui.pushButtonVideo2Browse.clicked.connect(self.browse_video2)
        self.ui.pushButtonOutputVideoBrowse.clicked.connect(self.browse_output_video)

        # Populate combo boxes
        self.populate_codec_comboboxes()
        self.populate_color_comboboxes()

        # Connect the clicked signal for audio source checkboxes
        self.ui.checkBoxOutputAudioVideo1.clicked.connect(self.update_audio_source)
        self.ui.checkBoxOutputAudioVideo2.clicked.connect(self.update_audio_source)

        # Connect the clicked signal for text position checkboxes
        self.ui.checkBoxVideo1AddTextBottom.clicked.connect(self.update_text_position_video1)
        self.ui.checkBoxVideo1AddTextTop.clicked.connect(self.update_text_position_video1)
        self.ui.checkBoxVideo1AddTextMiddle.clicked.connect(self.update_text_position_video1)
        self.ui.checkBoxVideo2AddTextBottom.clicked.connect(self.update_text_position_video2)
        self.ui.checkBoxVideo2AddTextTop.clicked.connect(self.update_text_position_video2)
        self.ui.checkBoxVideo2AddTextMiddle.clicked.connect(self.update_text_position_video2)

        self.font_cache = {}  # Initialize an empty dictionary for font_cache

    def start_font_scanning(self, splash):
        self.splash = splash
        self.font_scanner = FontScanner(os.path.join(os.environ['WINDIR'], 'Fonts'))
        self.font_scanner.update_signal.connect(lambda msg: splash.showMessage(msg, Qt.AlignBottom | Qt.AlignCenter, Qt.white))
        self.font_scanner.finished.connect(self.on_font_scanning_finished)
        self.font_scanner.start()

    def on_font_scanning_finished(self):
        self.font_cache = self.font_scanner.get_font_cache()
        self.splash.finish(self)
        self.show()  # Show the main window after the font scanning is complete and splash screen is closed

    def open_url(self):
        QDesktopServices.openUrl(QUrl("https://jmd.vc"))

    def populate_codec_comboboxes(self):
        # Common video codecs
        video_codecs = ['libx264', 'libx265', 'mpeg4', 'vp9', 'av1']
        self.ui.comboBoxVideoCodec.addItems(video_codecs)

        # Common audio codecs
        audio_codecs = ['aac', 'libmp3lame', 'opus', 'vorbis', 'flac']
        self.ui.comboBoxAudioCodec.addItems(audio_codecs)

    def populate_color_comboboxes(self):
        # Common colors
        colors = ['white', 'black', 'red', 'green', 'blue', 'yellow', 'purple', 'cyan', 'grey']
        self.ui.comboBoxVideoDividerColor.addItems(colors)
        self.ui.comboBoxVideo1AddTextColor.addItems(colors)
        self.ui.comboBoxVideo2AddTextColor.addItems(colors)

    def update_audio_source(self):
        sender = self.sender()
        if sender == self.ui.checkBoxOutputAudioVideo1 and sender.isChecked():
            self.ui.checkBoxOutputAudioVideo2.setChecked(False)
        elif sender == self.ui.checkBoxOutputAudioVideo2 and sender.isChecked():
            self.ui.checkBoxOutputAudioVideo1.setChecked(False)

    def update_text_position_video1(self):
        sender = self.sender()
        if sender.isChecked():
            self.ui.checkBoxVideo1AddTextBottom.setChecked(sender == self.ui.checkBoxVideo1AddTextBottom)
            self.ui.checkBoxVideo1AddTextTop.setChecked(sender == self.ui.checkBoxVideo1AddTextTop)
            self.ui.checkBoxVideo1AddTextMiddle.setChecked(sender == self.ui.checkBoxVideo1AddTextMiddle)

    def update_text_position_video2(self):
        sender = self.sender()
        if sender.isChecked():
            self.ui.checkBoxVideo2AddTextBottom.setChecked(sender == self.ui.checkBoxVideo2AddTextBottom)
            self.ui.checkBoxVideo2AddTextTop.setChecked(sender == self.ui.checkBoxVideo2AddTextTop)
            self.ui.checkBoxVideo2AddTextMiddle.setChecked(sender == self.ui.checkBoxVideo2AddTextMiddle)

    def browse_video1(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Video 1")
        if file_name:
            self.ui.lineEditVideo1.setText(file_name)

    def browse_video2(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Video 2")
        if file_name:
            self.ui.lineEditVideo2.setText(file_name)

    def browse_output_video(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Select Output Video File")
        if file_name:
            self.ui.lineEditOutputVideoFile.setText(file_name)

    def validate_time_format(self, time_str):
        return re.match(r"\d{2}:\d{2}:\d{2}", time_str) is not None

    # Method to get resolution from inputs
    def get_resolution(self, video_path):
        cmd = ["bin/ffprobe.exe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"ffprobe error: {result.stderr}")
            return (0, 0)

        match = re.match(r'(\d+)x(\d+)', result.stdout)
        return match.groups() if match else (0, 0)

    def scan_and_cache_fonts(self):
        self.append_to_output("Scanning system fonts...")
        font_dir = os.path.join(os.environ['WINDIR'], 'Fonts')
        for file in os.listdir(font_dir):
            font_path = os.path.join(font_dir, file)
            if os.path.isfile(font_path):
                # Add font and check families without creating QFontDatabase instance
                font_id = QFontDatabase.addApplicationFont(font_path)
                for family in QFontDatabase.applicationFontFamilies(font_id):
                    self.font_cache[family] = font_path
                    self.append_to_output(f"Cached font: {family}")
        self.append_to_output("Font scanning complete.")

    def get_font_path(self, font_family):
        return self.font_cache.get(font_family)

    def convert_font_path(self, font_path):
        return font_path.replace('\\', '/').replace(':', '\\:')

    def get_frame_rate(self, video_path, override_framerate=None):
        if override_framerate:
            try:
                float_override = float(override_framerate)
                return str(float_override)
            except ValueError:
                pass  # If override is not a valid float, proceed to extract frame rate

        cmd = ["bin/ffprobe.exe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"ffprobe error: {result.stderr}")
            return "25"  # Default frame rate in case of error

        # Calculate and return the frame rate
        try:
            num, den = result.stdout.strip().split('/')
            return str(int(num) / int(den))
        except Exception as e:
            logging.error(f"Error calculating frame rate: {e}")
            return "25"  # Default frame rate in case of error

    def process_videos(self):
        # Gather inputs from UI elements
        video1_path = self.ui.lineEditVideo1.text()
        video2_path = self.ui.lineEditVideo2.text()
        start_time_video1 = self.ui.lineEditStartTimeVideo1.text()
        start_time_video2 = self.ui.lineEditStartTimeVideo2.text()
        duration = self.ui.lineEditDuration.text()
        video_codec = self.ui.comboBoxVideoCodec.currentText()
        audio_codec = self.ui.comboBoxAudioCodec.currentText()
        bitrate = self.ui.lineEditBirate.text()
        divider_width = self.ui.lineEditOutputVideoDividerWidth.text()
        divider_color = self.ui.comboBoxVideoDividerColor.currentText()
        output_file = self.ui.lineEditOutputVideoFile.text()
        output_file_extension = self.ui.comboBoxOutputVideoType.currentText()
        use_audio_from_video1 = self.ui.checkBoxOutputAudioVideo1.isChecked()
        use_audio_from_video2 = self.ui.checkBoxOutputAudioVideo2.isChecked()

        # Get video resolutions
        res1 = self.get_resolution(video1_path)
        res2 = self.get_resolution(video2_path)

        # Check if resolution data is valid
        if res1 == (0, 0) or res2 == (0, 0):
            QMessageBox.critical(self, "Error", "Failed to obtain video resolutions. Check input file paths.")
            return

        # Calculate half width for cropping. Ensure it is an even number for YUV420 chroma subsampling
        half_width1 = int(res1[0]) // 2
        half_width2 = int(res2[0]) // 2

        # Adjust half_width to be even
        if half_width1 % 2 != 0:
            half_width1 -= 1
        if half_width2 % 2 != 0:
            half_width2 -= 1

        # Set a common height to the larger of both videos
        # common_height = max(int(res1[1]), int(res2[1]))

        # Calculate the starting x position for cropping the right half of video 2
        # crop_start_x_video2 = int(res2[0]) - half_width2

        # Retrieve the font path using the font family name
        font_video1 = self.ui.fontComboBoxVideo1.currentFont().family()
        font_path_video1_raw = self.font_cache.get(font_video1, '')  # Get raw font path
        font_path_video1 = self.convert_font_path(font_path_video1_raw)  # Convert to FFmpeg format

        font_video2 = self.ui.fontComboBoxVideo2.currentFont().family()
        font_path_video2_raw = self.font_cache.get(font_video2, '')  # Get raw font path
        font_path_video2 = self.convert_font_path(font_path_video2_raw)  # Convert to FFmpeg format

        text_video1 = self.ui.lineEditVideo1Text.text()
        text_video2 = self.ui.lineEditVideo2Text.text()
        color_video1 = self.ui.comboBoxVideo1AddTextColor.currentText()
        color_video2 = self.ui.comboBoxVideo2AddTextColor.currentText()

        # Determine text position for video 1
        text_position_video1 = "(h-text_h)/2"  # Middle by default
        if self.ui.checkBoxVideo1AddTextTop.isChecked():
            text_position_video1 = "10"  # Near the top
        elif self.ui.checkBoxVideo1AddTextBottom.isChecked():
            text_position_video1 = "h-text_h-10"  # Near the bottom

        # Determine text position for video 2
        text_position_video2 = "(h-text_h)/2"  # Middle by default
        if self.ui.checkBoxVideo2AddTextTop.isChecked():
            text_position_video2 = "10"  # Near the top
        elif self.ui.checkBoxVideo2AddTextBottom.isChecked():
            text_position_video2 = "h-text_h-10"  # Near the bottom

        # Start constructing the filter_complex string
        crop_scale_left = f"crop=iw/2:ih:0:0,scale=-2:{int(res2[1])}"
        crop_right = f"crop={int(res2[0])/2}:{int(res2[1])}:{int(res2[0])/2}:0"

        filter_complex = f"[0:v]{crop_scale_left}[left];[1:v]{crop_right}[right];"

        # Apply text overlays if checked
        if self.ui.checkBoxVideo1AddText.isChecked():
            filter_complex += f"[left]drawtext=text='{text_video1}':fontfile='{font_path_video1}':fontcolor={color_video1}:x=(w-text_w)/2:y={text_position_video1}[left];"
        if self.ui.checkBoxVideo2AddText.isChecked():
            filter_complex += f"[right]drawtext=text='{text_video2}':fontfile='{font_path_video2}':fontcolor={color_video2}:x=(w-text_w)/2:y={text_position_video2}[right];"

        # Combine left and right videos with divider
        if self.ui.checkBoxOutputVideoDivider.isChecked():
            divider_layout = f"|w0+{divider_width}_0"
        else:
            divider_layout = "|w0_0"

        filter_complex += f"[left][right]xstack=inputs=2:layout=0_0{divider_layout}:fill={divider_color}[v]"

        # Update output file extension
        output_file_extension = self.ui.comboBoxOutputVideoType.currentText()
        if not output_file.endswith(f".{output_file_extension}"):
            output_file = f"{output_file}.{output_file_extension}"

        # Construct the FFmpeg command
        cmd = [
            "bin/ffmpeg.exe",
            "-ss", str(start_time_video1),
            "-i", str(video1_path),
            "-ss", str(start_time_video2),
            "-i", str(video2_path),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-t", str(duration),
            "-c:v", str(video_codec),
            "-b:v", str(bitrate) + "k",
            str(output_file)
        ]

        # Determine audio mapping based on user selection
        if use_audio_from_video1:
            cmd.extend(["-map", "0:a", "-c:a", audio_codec])
        elif use_audio_from_video2:
            cmd.extend(["-map", "1:a", "-c:a", audio_codec])

        # Print the command to the output area
        self.append_to_output("FFmpeg command:\n" + " ".join(cmd))

        try:
            self.ffmpeg_thread = FFmpegThread(cmd)
            self.ffmpeg_thread.update_signal.connect(self.append_to_output)
            self.ffmpeg_thread.start()
        except Exception as e:
            logging.error(f"Error in process_videos: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def append_to_output(self, text):
        QApplication.processEvents()
        self.ui.plainTextEditOutput.appendPlainText(text)
        self.ui.plainTextEditOutput.moveCursor(QTextCursor.End)
        self.ui.plainTextEditOutput.ensureCursorVisible()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash_pix = QPixmap("images/splash.png")
    splash = QSplashScreen(splash_pix)
    splash.show()
    app.processEvents()

    main_window = MainWindow()
    main_window.start_font_scanning(splash)

    sys.exit(app.exec())
