import os
import sys
import csv
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox,
    QLineEdit, QLabel, QCheckBox, QMenu, QHeaderView, QDialog, QListWidget,
    QListWidgetItem, QDialogButtonBox, QInputDialog, QProgressDialog, QFrame
)


APP_NAME = "MP3 Merger"


AVAILABLE_COLUMNS = [
    ("filename", "Filename"),
    ("folder", "Folder"),
    ("full_path", "Full Path"),
    ("size_mb", "Size MB"),
    ("modified", "Modified"),
]


def ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None


def quote_concat_path(path: Path) -> str:
    # ffmpeg concat demuxer expects single-quoted paths, with internal single quotes escaped.
    s = str(path.resolve()).replace("\\", "/")
    s = s.replace("'", r"'\''")
    return f"file '{s}'"


def safe_output_path(folder: str, filename: str) -> Path:
    if not folder.strip():
        raise ValueError("Output folder is required.")
    if not filename.strip():
        raise ValueError("Output filename is required.")

    name = filename.strip()
    if not name.lower().endswith(".mp3"):
        name += ".mp3"

    invalid = '<>:"/\\|?*'
    if any(ch in Path(name).name for ch in invalid):
        raise ValueError('Output filename contains invalid Windows filename characters: <>:"/\\|?*')

    return Path(folder.strip()) / name

def metadata_album_value(output_path: Path, album_override: str) -> str:
    override = album_override.strip()
    if override:
        return override
    return output_path.parent.name


def metadata_title_value(output_path: Path) -> str:
    return output_path.stem

def split_into_three(items):
    n = len(items)
    base = n // 3
    rem = n % 3
    # Requirement: output 03 gets the extra 1 or 2 files.
    sizes = [base, base, base + rem]
    result = []
    start = 0
    for size in sizes:
        result.append(items[start:start + size])
        start += size
    return result


class ColumnDialog(QDialog):
    def __init__(self, active_keys, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Visible Columns")
        self.resize(360, 300)

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()

        for key, label in AVAILABLE_COLUMNS:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if key in active_keys else Qt.Unchecked)
            self.list_widget.addItem(item)

        layout.addWidget(QLabel("Select columns to show:"))
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_keys(self):
        keys = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                keys.append(item.data(Qt.UserRole))
        if "filename" not in keys:
            keys.insert(0, "filename")
        return keys


class DropTable(QTableWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSortingEnabled(False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls() or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = []
            for url in event.mimeData().urls():
                p = Path(url.toLocalFile())
                if p.is_dir():
                    paths.extend(sorted(p.glob("*.mp3")))
                elif p.is_file() and p.suffix.lower() in [".mp3", ".m4b"]:
                    paths.append(p)
            self.main_window.add_files(paths)
            event.acceptProposedAction()
        else:
            # Internal row move support.
            rows = sorted(set(i.row() for i in self.selectedIndexes()))
            if not rows:
                return
            drop_row = self.indexAt(event.position().toPoint()).row()
            if drop_row < 0:
                drop_row = self.rowCount()

            items_to_move = [self.main_window.files[r] for r in rows]
            remaining = [f for idx, f in enumerate(self.main_window.files) if idx not in rows]

            # Adjust destination when removing rows before the drop point.
            before_count = sum(1 for r in rows if r < drop_row)
            insert_at = max(0, drop_row - before_count)

            self.main_window.files = remaining[:insert_at] + items_to_move + remaining[insert_at:]
            self.main_window.refresh_table()
            self.main_window.select_rows(range(insert_at, insert_at + len(items_to_move)))
            event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1050, 650)

        self.files = []
        self.visible_columns = ["filename"]

        self.build_ui()
        self.build_actions()
        self.refresh_table()

        if not ffmpeg_exists():
            QMessageBox.warning(
                self,
                "ffmpeg not found",
                "ffmpeg was not found in PATH.\n\n"
                "The app can still open, but merge operations will fail until ffmpeg is installed "
                "and available from Command Prompt using: ffmpeg -version"
            )

    def build_ui(self):
        root = QWidget()
        main_layout = QVBoxLayout(root)

        top = QHBoxLayout()

        self.btn_add_folder = QPushButton("Add Folder")
        self.btn_add_files = QPushButton("Add Files")

        self.btn_merge_selected = QPushButton("Merge Selected")
        self.btn_merge_all = QPushButton("Merge All")

        self.btn_easy = QPushButton("Easy Button: Split into 3")
        self.btn_convert_m4b = QPushButton("Convert M4B to MP3")
        self.btn_convert_m4b.setEnabled(False)

        self.btn_remove_selected = QPushButton("Remove Selected")
        self.btn_clear = QPushButton("Clear All")
        self.chk_reencode = QCheckBox("Re-encode instead of fast copy")
        self.chk_zune = QCheckBox("Zune compatible MP3")
        self.chk_zune.setChecked(True)
        self.chk_zune.setToolTip(
            "Creates a conservative MP3 file for older software/devices: "
            "CBR, 44.1 kHz, stereo, ID3v2.3 tags."
        )


        def make_button_stack(*buttons):
            stack = QVBoxLayout()
            for button in buttons:
                stack.addWidget(button)
            return stack


        def make_divider():
            line = QFrame()
            line.setFrameShape(QFrame.VLine)
            line.setFrameShadow(QFrame.Sunken)
            return line


        top.addStretch()

        top.addLayout(make_button_stack(self.btn_add_folder, self.btn_add_files))
        top.addSpacing(30)
        top.addWidget(make_divider())
        top.addSpacing(30)

        top.addLayout(make_button_stack(self.btn_merge_selected, self.btn_merge_all))
        top.addSpacing(30)
        top.addWidget(make_divider())
        top.addSpacing(30)

        top.addLayout(make_button_stack(self.btn_easy, self.btn_convert_m4b))
        top.addSpacing(30)
        top.addWidget(make_divider())
        top.addSpacing(30)

        top.addLayout(make_button_stack(self.btn_remove_selected, self.btn_clear))
        top.addSpacing(30)
        top.addWidget(make_divider())
        top.addSpacing(30)

        top.addLayout(make_button_stack(self.chk_reencode, self.chk_zune))

        top.addStretch()

        main_layout.addLayout(top)

        output = QHBoxLayout()
        self.output_folder = QLineEdit()
        self.output_folder.setPlaceholderText("Output folder")
        self.btn_browse_output = QPushButton("Browse Output Folder")
        self.output_filename = QLineEdit()
        self.output_filename.setPlaceholderText("Output filename, e.g. My Audiobook")

        self.album_override = QLineEdit()
        self.album_override.setPlaceholderText("Optional album override; blank = output folder name")


        self.chk_zune.setChecked(True)
        self.chk_zune.setToolTip(
            "Creates a conservative MP3 file for older software/devices: "
            "CBR, 44.1 kHz, stereo, ID3v2.3 tags."
        )

        output.addWidget(QLabel("Folder:"))
        output.addWidget(self.output_folder, 2)
        output.addWidget(self.btn_browse_output)
        output.addWidget(QLabel("Filename:"))
        output.addWidget(self.output_filename, 2)
        output.addWidget(QLabel("Album:"))
        output.addWidget(self.album_override, 2)

        main_layout.addLayout(output)

        self.table = DropTable(self)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        main_layout.addWidget(self.table)

        hint = QLabel(
            "Tip: drag MP3 files or folders into the list. Default sort is filename ascending. "
            "To manually sort, drag selected rows within the list."
        )
        main_layout.addWidget(hint)

        self.setCentralWidget(root)

        self.btn_add_folder.clicked.connect(self.add_folder_dialog)
        self.btn_add_files.clicked.connect(self.add_files_dialog)
        self.btn_merge_selected.clicked.connect(self.merge_selected)
        self.btn_merge_all.clicked.connect(self.merge_all)
        self.btn_easy.clicked.connect(self.easy_button)
        self.btn_convert_m4b.clicked.connect(self.convert_selected_m4b)
        self.table.itemSelectionChanged.connect(self.update_m4b_button_state)
        self.btn_remove_selected.clicked.connect(self.remove_selected)
        self.btn_clear.clicked.connect(self.clear_all)
        self.btn_browse_output.clicked.connect(self.browse_output_folder)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def build_actions(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        add_folder = QAction("Add Folder", self)
        add_files = QAction("Add Files", self)
        exit_action = QAction("Exit", self)
        add_folder.triggered.connect(self.add_folder_dialog)
        add_files.triggered.connect(self.add_files_dialog)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(add_folder)
        file_menu.addAction(add_files)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("Edit")
        sort_filename = QAction("Sort by Filename Asc", self)
        columns = QAction("Choose Columns", self)
        remove_selected = QAction("Remove Selected", self)
        clear_all = QAction("Clear All", self)
        sort_filename.triggered.connect(self.sort_by_filename)
        columns.triggered.connect(self.choose_columns)
        remove_selected.triggered.connect(self.remove_selected)
        clear_all.triggered.connect(self.clear_all)
        edit_menu.addAction(sort_filename)
        edit_menu.addAction(columns)
        edit_menu.addSeparator()
        edit_menu.addAction(remove_selected)
        edit_menu.addAction(clear_all)

        merge_menu = menubar.addMenu("Merge")
        merge_selected = QAction("Merge Selected", self)
        merge_all = QAction("Merge All", self)
        easy = QAction("Easy Button: Split into 3", self)
        merge_selected.triggered.connect(self.merge_selected)
        merge_all.triggered.connect(self.merge_all)
        easy.triggered.connect(self.easy_button)
        merge_menu.addAction(merge_selected)
        merge_menu.addAction(merge_all)
        merge_menu.addAction(easy)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Merge Selected", self.merge_selected)
        menu.addAction("Merge All", self.merge_all)
        menu.addAction("Easy Button: Split into 3", self.easy_button)
        menu.addSeparator()
        menu.addAction("Sort by Filename Asc", self.sort_by_filename)
        menu.addAction("Choose Columns", self.choose_columns)
        menu.addSeparator()
        menu.addAction("Remove Selected", self.remove_selected)
        menu.addAction("Clear All", self.clear_all)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder containing MP3 files")
        if folder:
            paths = sorted(Path(folder).glob("*.mp3"))
            self.add_files(paths)

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select MP3 files",
            "",
            "Audio files (*.mp3 *.m4b)"
        )
        self.add_files([Path(p) for p in paths])

    def add_files(self, paths):
        existing = {str(p.resolve()).lower() for p in self.files}
        added = 0
        for p in paths:
            p = Path(p)
            if p.is_file() and p.suffix.lower() in [".mp3", ".m4b"]:
                key = str(p.resolve()).lower()
                if key not in existing:
                    self.files.append(p.resolve())
                    existing.add(key)
                    added += 1

        self.sort_by_filename(refresh=False)
        self.refresh_table()

        if added == 0 and paths:
            QMessageBox.information(self, "No files added", "No new .mp3 files were added.")

    def sort_by_filename(self, refresh=True):
        self.files.sort(key=lambda p: p.name.lower())
        if refresh:
            self.refresh_table()

    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select output folder")
        if folder:
            self.output_folder.setText(folder)

    def choose_columns(self):
        dlg = ColumnDialog(self.visible_columns, self)
        if dlg.exec() == QDialog.Accepted:
            self.visible_columns = dlg.selected_keys()
            self.refresh_table()

    def file_value(self, path: Path, key: str):
        stat = path.stat()
        if key == "filename":
            return path.name
        if key == "folder":
            return str(path.parent)
        if key == "full_path":
            return str(path)
        if key == "size_mb":
            return f"{stat.st_size / (1024 * 1024):.2f}"
        if key == "modified":
            import datetime
            return datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        return ""

    def refresh_table(self):
        self.table.setColumnCount(len(self.visible_columns))
        labels = [dict(AVAILABLE_COLUMNS)[k] for k in self.visible_columns]
        self.table.setHorizontalHeaderLabels(labels)
        self.table.setRowCount(len(self.files))
        self.update_m4b_button_state()

        for r, path in enumerate(self.files):
            for c, key in enumerate(self.visible_columns):
                item = QTableWidgetItem(self.file_value(path, key))
                item.setData(Qt.UserRole, str(path))
                self.table.setItem(r, c, item)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def select_rows(self, rows):
        self.table.clearSelection()
        for r in rows:
            self.table.selectRow(r)

    def selected_paths(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()))
        return [self.files[r] for r in rows]

    def remove_selected(self):
        rows = sorted(set(idx.row() for idx in self.table.selectedIndexes()), reverse=True)
        for r in rows:
            del self.files[r]
        self.refresh_table()

    def clear_all(self):
        if not self.files:
            return
        reply = QMessageBox.question(self, "Clear All", "Remove all files from the list?")
        if reply == QMessageBox.Yes:
            self.files.clear()
            self.refresh_table()

    def update_m4b_button_state(self):
        selected = self.selected_paths()
        enabled = len(selected) == 1 and selected[0].suffix.lower() == ".m4b"
        self.btn_convert_m4b.setEnabled(enabled)

    def convert_selected_m4b(self):
        selected = self.selected_paths()

        if len(selected) != 1 or selected[0].suffix.lower() != ".m4b":
            QMessageBox.information(
                self,
                "Select one M4B",
                "Select exactly one .m4b file to convert."
            )
            return

        source_path = selected[0]

        try:
            out = safe_output_path(self.output_folder.text(), self.output_filename.text())
        except ValueError as e:
            QMessageBox.warning(self, "Output Required", str(e))
            return

        if out.suffix.lower() != ".mp3":
            out = out.with_suffix(".mp3")

        ok = self.run_ffmpeg_convert_m4b(source_path, out)

        if ok:
            QMessageBox.information(self, "Done", f"M4B conversion complete:\n{out}")

    def merge_selected(self):
        paths = self.selected_paths()
        if not paths:
            QMessageBox.information(self, "No selection", "Select one or more MP3 files first.")
            return
        self.merge_paths(paths, suffix=None)

    def merge_all(self):
        if not self.files:
            QMessageBox.information(self, "No files", "Add MP3 files first.")
            return
        self.merge_paths(list(self.files), suffix=None)

    def easy_button(self):
        if len(self.files) < 3:
            QMessageBox.information(self, "Not enough files", "Add at least 3 MP3 files for the Easy Button.")
            return

        try:
            base = safe_output_path(self.output_folder.text(), self.output_filename.text())
        except ValueError as e:
            QMessageBox.warning(self, "Output Required", str(e))
            return

        groups = split_into_three(list(self.files))
        for idx, group in enumerate(groups, start=1):
            if not group:
                continue
            out = base.with_name(f"{base.stem}_{idx:02d}{base.suffix}")
            ok = self.run_ffmpeg_merge(group, out, self.chk_reencode.isChecked())
            if not ok:
                return

        QMessageBox.information(self, "Done", "Easy Button merge complete.")

    def merge_paths(self, paths, suffix=None):
        try:
            out = safe_output_path(self.output_folder.text(), self.output_filename.text())
        except ValueError as e:
            QMessageBox.warning(self, "Output Required", str(e))
            return

        if suffix:
            out = out.with_name(f"{out.stem}_{suffix}{out.suffix}")

        ok = self.run_ffmpeg_merge(paths, out, self.chk_reencode.isChecked())
        if ok:
            QMessageBox.information(self, "Done", f"Merge complete:\n{out}")

    def run_ffmpeg_convert_m4b(self, source_path: Path, output_path: Path):
            if not ffmpeg_exists():
                QMessageBox.critical(
                    self,
                    "ffmpeg missing",
                    "ffmpeg is not available in PATH.\n\n"
                    "Install ffmpeg and confirm this works in Command Prompt:\nffmpeg -version"
                )
                return False

            output_path.parent.mkdir(parents=True, exist_ok=True)

            if output_path.exists():
                reply = QMessageBox.question(
                    self,
                    "Overwrite file?",
                    f"The output file already exists:\n{output_path}\n\nOverwrite it?"
                )
                if reply != QMessageBox.Yes:
                    return False

            album_value = metadata_album_value(output_path, self.album_override.text())
            title_value = metadata_title_value(output_path)
            log_path = output_path.with_suffix(".ffmpeg.log")

            cmd = [
                "ffmpeg", "-y",
                "-i", str(source_path),
                "-vn",
                "-map_metadata", "-1",
                "-id3v2_version", "3",
                "-write_id3v1", "1",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "128k",
                "-c:a", "libmp3lame",
                "-f", "mp3",
                "-metadata", "genre=Podcast",
                "-metadata", f"album={album_value}",
                "-metadata", f"title={title_value}",
                str(output_path)
            ]

            progress = QProgressDialog("Converting M4B to MP3...", "Cancel", 0, 0, self)
            progress.setWindowTitle("Working")
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            QApplication.processEvents()

            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )

            except Exception as e:
                progress.close()
                QMessageBox.critical(self, "Conversion failed", f"Could not run ffmpeg:\n{e}")
                return False

            progress.close()

            log_path.write_text(
                "COMMAND:\n"
                + " ".join(cmd)
                + "\n\nSTDOUT:\n"
                + proc.stdout
                + "\n\nSTDERR:\n"
                + proc.stderr,
                encoding="utf-8"
            )

            if proc.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
                QMessageBox.critical(
                    self,
                    "Conversion failed",
                    f"The M4B conversion failed.\n\nffmpeg log saved here:\n{log_path}"
                )
                return False

            return True

    def run_ffmpeg_merge(self, paths, output_path: Path, reencode: bool):
        if not ffmpeg_exists():
            QMessageBox.critical(
                self,
                "ffmpeg missing",
                "ffmpeg is not available in PATH.\n\n"
                "Install ffmpeg and confirm this works in Command Prompt:\nffmpeg -version"
            )
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists():
            reply = QMessageBox.question(
                self,
                "Overwrite file?",
                f"The output file already exists:\n{output_path}\n\nOverwrite it?"
            )
            if reply != QMessageBox.Yes:
                return False

        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".txt",
            delete=False,
            encoding="utf-8",
            newline="\n"
        ) as f:
            list_path = Path(f.name)

            for p in paths:
                f.write(quote_concat_path(p) + "\n")

        log_path = output_path.with_suffix(".ffmpeg.log")
        album_value = metadata_album_value(output_path, self.album_override.text())
        title_value = metadata_title_value(output_path)

        if self.chk_zune.isChecked():
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(list_path),
                "-vn",
                "-map_metadata", "-1",
                "-id3v2_version", "3",
                "-write_id3v1", "1",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "128k",
                "-c:a", "libmp3lame",
                "-f", "mp3",
                "-metadata", "genre=Podcast",
                "-metadata", f"album={album_value}",
                "-metadata", f"title={title_value}",
                str(output_path)
            ]

        elif reencode:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(list_path),
                "-vn",
                "-id3v2_version", "3",
                "-write_id3v1", "1",
                "-c:a", "libmp3lame",
                "-q:a", "2",
                "-f", "mp3",
                "-metadata", "genre=Podcast",
                "-metadata", f"album={album_value}",
                "-metadata", f"title={title_value}",
                str(output_path)
            ]

        else:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(list_path),
                "-c", "copy",
                "-id3v2_version", "3",
                "-write_id3v1", "1",
                "-f", "mp3",
                "-metadata", "genre=Podcast",
                "-metadata", f"album={album_value}",
                "-metadata", f"title={title_value}",
                str(output_path)
            ]

        progress = QProgressDialog("Merging MP3 files...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Working")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )

        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Merge failed", f"Could not run ffmpeg:\n{e}")
            return False

        finally:
            try:
                list_path.unlink(missing_ok=True)
            except Exception:
                pass

        progress.close()

        log_path.write_text(
            "COMMAND:\n"
            + " ".join(cmd)
            + "\n\nSTDOUT:\n"
            + proc.stdout
            + "\n\nSTDERR:\n"
            + proc.stderr,
            encoding="utf-8"
        )

        if proc.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:

            if not reencode:
                QMessageBox.warning(
                    self,
                    "Fast merge failed",
                    "The fast no-reencode merge failed.\n\n"
                    "This usually happens when the source MP3 files have incompatible stream parameters "
                    "or unusual metadata.\n\n"
                    "Recommendation: check 'Re-encode instead of fast copy' and try again.\n\n"
                    f"ffmpeg log saved here:\n{log_path}"
                )

            else:
                QMessageBox.critical(
                    self,
                    "Merge failed",
                    f"The re-encode merge also failed.\n\nffmpeg log saved here:\n{log_path}"
                )

            return False

        return True


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()