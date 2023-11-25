# This Python file uses the following encoding: utf-8
import sys
import subprocess
import re
from threading import Thread
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PySide6.QtGui import QTextCursor, QDesktopServices
from PySide6.QtCore import QUrl
import logging

# Setup logging
logging.basicConfig(filename='app.log', filemode='w', format='%(name)s - %(levelname)s - %(message)s')

# Import the UI layout
from ui_form import Ui_MainWindow

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

    def open_url(self):
        QDesktopServices.openUrl(QUrl("https://jmd.vc"))

    def append_to_output(self, text):
        self.ui.plainTextEditOutput.appendPlainText(text)
        self.ui.plainTextEditOutput.moveCursor(QTextCursor.End)  # Move cursor to end
        self.ui.plainTextEditOutput.ensureCursorVisible()  # Ensure new text is visible

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
        cmd = ["bin/ffmpeg.exe", "-i", video_path]  # Update path to ffmpeg if needed
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        match = re.search(r'(\d{2,})x(\d{2,})', result.stderr)
        return match.groups() if match else (0, 0)

    def process_videos(self):
        # Gather inputs from UI elements
        video1_path = self.ui.lineEditVideo1.text()
        video2_path = self.ui.lineEditVideo2.text()
        start_time = self.ui.lineEditStartTimeVideo1.text()
        duration = self.ui.lineEditDuration.text()
        framerate = self.ui.lineEditFPS.text()
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

        # Calculate half width for cropping and ensure it's even
        half_width1 = (int(res1[0]) // 2) - ((int(res1[0]) // 2) % 2)
        half_width2 = (int(res2[0]) // 2) - ((int(res2[0]) // 2) % 2)

        # Set a common height to the larger of both videos
        common_height = max(int(res1[1]), int(res2[1]))

        # Calculate the starting x position for cropping the right half of video 2
        crop_start_x_video2 = int(res2[0]) - half_width2

        # Get selected fonts and text
        font_video1 = self.ui.fontComboBoxVideo1.currentFont().family()
        font_video2 = self.ui.fontComboBoxVideo2.currentFont().family()
        text_video1 = self.ui.lineEditVideo1Text.text()
        text_video2 = self.ui.lineEditVideo2Text.text()

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

        # Construct FFmpeg filter_complex string
        filter_complex = f"[0:v]crop={half_width1}:ih:0:0,scale={half_width1}:{common_height}[left];"
        filter_complex += f"[1:v]crop={half_width2}:ih:{crop_start_x_video2}:0,scale={half_width2}:{common_height}[right];"

        # Apply text overlays if checked
        if self.ui.checkBoxVideo1AddText.isChecked():
            filter_complex += f"[left]drawtext=text='{text_video1}':fontfile='{font_video1}':x=(w-text_w)/2:y={text_position_video1}[left];"
        if self.ui.checkBoxVideo2AddText.isChecked():
            filter_complex += f"[right]drawtext=text='{text_video2}':fontfile='{font_video2}':x=(w-text_w)/2:y={text_position_video2}[right];"

        # Combine left and right videos with divider
        filter_complex += f"[left][right]xstack=inputs=2:layout=0_0|w0_{divider_width}:fill={divider_color}[v]"

        # Update output file extension
        output_file_extension = self.ui.comboBoxOutputVideoType.currentText()
        if not output_file.endswith(f".{output_file_extension}"):
            output_file = f"{output_file}.{output_file_extension}"

        try:
            # Construct the FFmpeg command
            cmd = [
                "bin/ffmpeg.exe",  # Replace with the correct path to ffmpeg
                "-ss", start_time,
                "-t", duration,
                "-i", video1_path,
                "-i", video2_path,
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-r", framerate,
                "-c:v", video_codec,
                "-b:v", f"{bitrate}k",
                output_file
            ]

            # Determine audio mapping based on user selection
            if use_audio_from_video1:
                cmd.extend(["-map", "0:a", "-c:a", audio_codec])
            elif use_audio_from_video2:
                cmd.extend(["-map", "1:a", "-c:a", audio_codec])

            # Run the FFmpeg command in a separate thread
            thread = Thread(target=self.run_ffmpeg_command, args=(cmd,))
            thread.start()
        except Exception as e:
            logging.error(f"Error in process_videos: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def run_ffmpeg_command(self, cmd):
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                # Standardize line endings
                standardized_line = line.replace('\r\n', '\n').replace('\r', '\n')
                self.append_to_output(standardized_line.strip())  # Remove leading/trailing whitespace
                QApplication.processEvents()  # Update GUI
            process.wait()
            self.statusBar().showMessage("Processing completed successfully.")
        except Exception as e:
            # Log and inform of the error
            logging.error(f"FFmpeg subprocess error: {e}")
            self.append_to_output(f"Error: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec())
