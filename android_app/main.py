import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp, sp
from kivy.properties import (
    BooleanProperty,
    ColorProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.animation import Animation
from kivy.utils import get_color_from_hex

from kivymd.app import MDApp
from kivymd.uix.button import MDIconButton, MDRaisedButton, MDRectangleFlatButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import IRightBodyTouch, OneLineAvatarIconListItem
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.snackbar import MDSnackbar
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.utils import asynckivy

from downloader import Downloader, MediaInfo, QUALITY_LABELS

try:
    from android.permissions import Permission, request_permissions
    HAS_ANDROID = True
except Exception:
    HAS_ANDROID = False


PRIMARY = "#1a73e8"
PRIMARY_DARK = "#0d47a1"
SURFACE = "#1e1e1e"
BACKGROUND = "#121212"
ERROR = "#cf6679"
ON_SURFACE = "#e0e0e0"
ON_BACKGROUND = "#ffffff"

KV = """
<NovaScreenManager>:
    transition: SlideTransition(duration=0.3)

<HomeScreen>:
    BoxLayout:
        orientation: "vertical"
        spacing: 0

        MDTopAppBar:
            title: "Nova Downloader"
            md_bg_color: app.theme_cls.primary_color
            specific_text_color: 1, 1, 1, 1
            elevation: 4
            left_action_items: [["menu", lambda x: None]]

        ScrollView:
            id: scroll
            BoxLayout:
                orientation: "vertical"
                padding: [dp(16), dp(16), dp(16), dp(16)]
                spacing: dp(16)
                size_hint_y: None
                height: self.minimum_height

                MDCard:
                    orientation: "vertical"
                    padding: dp(16)
                    spacing: dp(12)
                    size_hint_y: None
                    height: dp(220)
                    md_bg_color: app.theme_cls.bg_light

                    MDTextField:
                        id: url_input
                        hint_text: "Paste video URL here"
                        mode: "fill"
                        fill_color: 0.15, 0.15, 0.15, 1
                        line_color_normal: 0.3, 0.3, 0.3, 1
                        text_color_normal: 1, 1, 1, 1
                        hint_text_color_normal: 0.5, 0.5, 0.5, 1
                        icon_right: "link-variant"
                        icon_right_color: 0.5, 0.5, 0.5, 1
                        size_hint_x: 1
                        multiline: False

                    MDRaisedButton:
                        text: "Analyse URL"
                        size_hint_x: 1
                        height: dp(52)
                        md_bg_color: app.theme_cls.primary_color
                        text_color: 1, 1, 1, 1
                        font_size: sp(16)
                        on_release: app.on_analyse()

                MDCard:
                    id: info_card
                    orientation: "vertical"
                    padding: dp(16)
                    spacing: dp(8)
                    size_hint_y: None
                    height: dp(0)
                    md_bg_color: app.theme_cls.bg_light
                    opacity: 0
                    disabled: True

                    BoxLayout:
                        orientation: "horizontal"
                        size_hint_y: None
                        height: dp(60)
                        spacing: dp(12)

                        BoxLayout:
                            orientation: "vertical"
                            size_hint_x: 0.7
                            spacing: dp(4)

                            Label:
                                id: title_label
                                text: ""
                                font_size: sp(16)
                                bold: True
                                color: 1, 1, 1, 1
                                halign: "left"
                                text_size: self.width, None
                                size_hint_y: 0.6

                            Label:
                                id: info_label
                                text: ""
                                font_size: sp(13)
                                color: 0.6, 0.6, 0.6, 1
                                halign: "left"
                                text_size: self.width, None
                                size_hint_y: 0.4

                        MDRaisedButton:
                            id: quality_btn
                            text: "Quality"
                            size_hint_x: 0.3
                            size_hint_y: None
                            height: dp(44)
                            md_bg_color: app.theme_cls.primary_color
                            text_color: 1, 1, 1, 1
                            on_release: app.show_quality_menu()

                    MDRaisedButton:
                        id: download_btn
                        text: "Download"
                        size_hint_x: 1
                        height: dp(52)
                        md_bg_color: app.theme_cls.primary_color
                        text_color: 1, 1, 1, 1
                        font_size: sp(16)
                        disabled: True
                        on_release: app.start_download()

                MDCard:
                    id: progress_card
                    orientation: "vertical"
                    padding: dp(16)
                    spacing: dp(12)
                    size_hint_y: None
                    height: dp(0)
                    md_bg_color: app.theme_cls.bg_light
                    opacity: 0
                    disabled: True

                    Label:
                        id: status_label
                        text: "Preparing..."
                        font_size: sp(14)
                        color: 1, 1, 1, 1
                        size_hint_y: None
                        height: dp(24)

                    MDProgressBar:
                        id: progress_bar
                        value: 0
                        size_hint_x: 1
                        size_hint_y: None
                        height: dp(6)
                        color: app.theme_cls.primary_color

                    BoxLayout:
                        orientation: "horizontal"
                        size_hint_y: None
                        height: dp(20)
                        spacing: dp(8)

                        Label:
                            id: progress_label
                            text: "0%"
                            font_size: sp(12)
                            color: 0.6, 0.6, 0.6, 1
                            size_hint_x: 0.33

                        Label:
                            id: speed_label
                            text: ""
                            font_size: sp(12)
                            color: 0.6, 0.6, 0.6, 1
                            size_hint_x: 0.33
                            halign: "center"

                        Label:
                            id: eta_label
                            text: ""
                            font_size: sp(12)
                            color: 0.6, 0.6, 0.6, 1
                            size_hint_x: 0.33
                            halign: "right"

                    MDRectangleFlatButton:
                        text: "Cancel"
                        size_hint_x: 1
                        height: dp(44)
                        text_color: app.theme_cls.error_color
                        line_color: app.theme_cls.error_color
                        on_release: app.cancel_download()

<HistoryScreen>:
    BoxLayout:
        orientation: "vertical"
        spacing: 0

        MDTopAppBar:
            title: "Downloads"
            md_bg_color: app.theme_cls.primary_color
            specific_text_color: 1, 1, 1, 1
            elevation: 4

        ScrollView:
            id: history_scroll
            BoxLayout:
                id: history_list
                orientation: "vertical"
                padding: [dp(8), dp(8), dp(8), dp(8)]
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height

<HistoryItem>:
    size_hint_y: None
    height: dp(80)
    padding: dp(12)
    spacing: dp(8)
    md_bg_color: app.theme_cls.bg_light
    radius: [dp(12)]

    BoxLayout:
        orientation: "vertical"
        size_hint_x: 0.75
        spacing: dp(4)

        Label:
            text: root.title_text
            font_size: sp(14)
            bold: True
            color: 1, 1, 1, 1
            halign: "left"
            text_size: self.width, None
            size_hint_y: 0.5

        BoxLayout:
            orientation: "horizontal"
            size_hint_y: 0.5
            spacing: dp(8)

            Label:
                text: root.quality_text
                font_size: sp(12)
                color: 0.5, 0.5, 0.5, 1
                size_hint_x: 0.3

            Label:
                text: root.date_text
                font_size: sp(12)
                color: 0.5, 0.5, 0.5, 1
                size_hint_x: 0.4

            Label:
                text: "Open"
                font_size: sp(12)
                color: app.theme_cls.primary_color
                bold: True
                size_hint_x: 0.3
                halign: "right"

    MDRaisedButton:
        text: "Open"
        size_hint_x: 0.25
        size_hint_y: None
        height: dp(36)
        md_bg_color: app.theme_cls.primary_color
        text_color: 1, 1, 1, 1
        pos_hint: {"center_y": 0.5}
        on_release: root.open_file()
"""


class HistoryItem(MDCard):
    title_text = StringProperty()
    quality_text = StringProperty()
    date_text = StringProperty()
    file_path = StringProperty()

    def open_file(self):
        path = self.file_path
        if path and os.path.exists(path):
            try:
                from jnius import autoclass
                Intent = autoclass("android.content.Intent")
                Uri = autoclass("android.net.Uri")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = PythonActivity.mActivity
                intent = Intent(Intent.ACTION_VIEW)
                uri = Uri.parse("file://" + path)
                intent.setDataAndType(uri, self._get_mime(path))
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                activity.startActivity(intent)
            except Exception:
                pass

    @staticmethod
    def _get_mime(path: str) -> str:
        if path.endswith(".mp3"):
            return "audio/mpeg"
        return "video/mp4"


class HomeScreen(Screen):
    pass


class HistoryScreen(Screen):
    pass


class NovaScreenManager(ScreenManager):
    pass


class NovaDownloaderApp(MDApp):
    downloader = ObjectProperty(Downloader())
    current_media = ObjectProperty(None, allownone=True)
    selected_quality = StringProperty("")
    is_downloading = BooleanProperty(False)
    download_thread = ObjectProperty(None, allownone=True)
    history_file = StringProperty("")

    def build(self):
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.material_style = "M3"
        self.theme_cls.bg_light = get_color_from_hex(SURFACE)

        self.history_file = str(self._get_data_dir() / "history.json")

        sm = NovaScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(HistoryScreen(name="history"))
        return sm

    def on_start(self):
        if HAS_ANDROID:
            request_permissions(
                [Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE]
            )
        self._load_history()

    def _get_data_dir(self) -> Path:
        try:
            from android.storage import primary_external_storage_path
            base = Path(primary_external_storage_path()) / "NovaDownloader"
        except Exception:
            base = Path(__file__).parent / "data"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def on_analyse(self):
        screen = self.root.get_screen("home")
        url = screen.ids.url_input.text.strip()
        if not url:
            self._show_error("Please enter a URL")
            return

        screen.ids.info_card.opacity = 0
        screen.ids.info_card.height = 0
        screen.ids.info_card.disabled = True

        thread = threading.Thread(target=self._do_analyse, args=(url,), daemon=True)
        thread.start()

    def _do_analyse(self, url: str):
        try:
            info = self.downloader.analyse(url)
            Clock.schedule_once(lambda dt: self._on_analyse_result(info))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._show_error(str(e)))

    def _on_analyse_result(self, info: MediaInfo):
        screen = self.root.get_screen("home")
        screen.ids.title_label.text = info.title
        screen.ids.info_label.text = (
            f"{info.media_type}  |  {info.duration_str}  |  {len(info.available)} qualities"
        )
        screen.ids.quality_btn.text = info.available[0] if info.available else "N/A"
        self.selected_quality = info.available[0] if info.available else ""
        self.current_media = info

        screen.ids.download_btn.disabled = not bool(info.available)
        screen.ids.info_card.disabled = False
        screen.ids.info_card.height = dp(150)
        screen.ids.info_card.opacity = 1

        Animation(opacity=1, height=dp(150), duration=0.3).start(screen.ids.info_card)

    def show_quality_menu(self):
        if not self.current_media:
            return
        screen = self.root.get_screen("home")
        btn = screen.ids.quality_btn

        menu_items = [
            {
                "text": q,
                "viewclass": "OneLineListItem",
                "on_release": lambda q=q: self._select_quality(q),
            }
            for q in self.current_media.available
        ]

        self._quality_menu = MDDropdownMenu(
            caller=btn,
            items=menu_items,
            width_mult=4,
            radius=[dp(12)],
        )
        self._quality_menu.open()

    def _select_quality(self, quality: str):
        self.selected_quality = quality
        screen = self.root.get_screen("home")
        screen.ids.quality_btn.text = quality
        if hasattr(self, "_quality_menu"):
            self._quality_menu.dismiss()

    def start_download(self):
        if self.is_downloading or not self.current_media or not self.selected_quality:
            return
        self.is_downloading = True

        screen = self.root.get_screen("home")
        screen.ids.download_btn.disabled = True
        screen.ids.progress_card.disabled = False
        screen.ids.progress_card.height = dp(160)
        screen.ids.progress_card.opacity = 1
        screen.ids.progress_bar.value = 0
        screen.ids.progress_label.text = "0%"
        screen.ids.status_label.text = "Starting..."
        screen.ids.speed_label.text = ""
        screen.ids.eta_label.text = ""

        Animation(opacity=1, height=dp(160), duration=0.3).start(screen.ids.progress_card)

        self.download_thread = threading.Thread(
            target=self._do_download, daemon=True
        )
        self.download_thread.start()

    def _do_download(self):
        def callback(p: Dict[str, Any]):
            Clock.schedule_once(lambda dt: self._update_progress(p))

        try:
            path = self.downloader.download(
                self.current_media.url,
                self.selected_quality,
                progress_callback=callback,
            )
            Clock.schedule_once(lambda dt: self._on_download_complete(str(path)))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._on_download_error(str(e)))

    def _update_progress(self, p: Dict[str, Any]):
        screen = self.root.get_screen("home")
        stage = p.get("stage", "")

        if stage == "downloading":
            percent = p.get("percent", 0)
            screen.ids.progress_bar.value = percent
            screen.ids.progress_label.text = f"{percent:.1f}%"
            screen.ids.status_label.text = p.get("message", "Downloading...")

            speed = p.get("speed")
            if speed:
                screen.ids.speed_label.text = self._format_speed(speed)
            eta = p.get("eta")
            if eta is not None and eta >= 0:
                screen.ids.eta_label.text = self._format_eta(eta)
        else:
            screen.ids.status_label.text = p.get("message", "Processing...")

    def _on_download_complete(self, path: str):
        self.is_downloading = False
        screen = self.root.get_screen("home")
        screen.ids.progress_bar.value = 100
        screen.ids.progress_label.text = "100%"
        screen.ids.status_label.text = "Complete!"
        screen.ids.speed_label.text = ""
        screen.ids.eta_label.text = ""

        self._save_history(
            self.current_media.title,
            self.current_media.url,
            self.selected_quality,
            path,
        )
        self._load_history()

        Clock.schedule_once(lambda dt: self._reset_ui(), 2)

        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            intent = Intent(Intent.ACTION_VIEW)
            uri = Uri.parse("file://" + path)
            mime = "audio/mpeg" if path.endswith(".mp3") else "video/mp4"
            intent.setDataAndType(uri, mime)
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            activity.startActivity(intent)
        except Exception:
            pass

    def _on_download_error(self, error: str):
        self.is_downloading = False
        self._show_error(error)
        self._reset_ui()

    def _reset_ui(self):
        screen = self.root.get_screen("home")
        screen.ids.progress_card.disabled = True
        screen.ids.progress_card.height = 0
        screen.ids.progress_card.opacity = 0
        screen.ids.download_btn.disabled = False

    def cancel_download(self):
        self.downloader.cancel()
        self.is_downloading = False
        screen = self.root.get_screen("home")
        screen.ids.status_label.text = "Cancelled"
        Clock.schedule_once(lambda dt: self._reset_ui(), 1)

    def _save_history(self, title: str, url: str, quality: str, path: str):
        entries = []
        if os.path.exists(self.history_file):
            try:
                entries = json.loads(Path(self.history_file).read_text(encoding="utf-8"))
            except Exception:
                pass
        entries.append({
            "title": title,
            "url": url,
            "quality": quality,
            "path": path,
            "date": time.strftime("%Y-%m-%d %H:%M"),
        })
        entries = entries[-50:]
        Path(self.history_file).write_text(
            json.dumps(entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_history(self):
        screen = self.root.get_screen("history")
        history_list = screen.ids.history_list
        history_list.clear_widgets()

        if not os.path.exists(self.history_file):
            no_data = Label(
                text="No downloads yet",
                font_size=sp(16),
                color=(0.5, 0.5, 0.5, 1),
                size_hint_y=None,
                height=dp(200),
            )
            history_list.add_widget(no_data)
            return

        try:
            entries = json.loads(Path(self.history_file).read_text(encoding="utf-8"))
        except Exception:
            return

        for entry in reversed(entries[-30:]):
            item = HistoryItem(
                title_text=entry.get("title", "Unknown"),
                quality_text=entry.get("quality", "N/A"),
                date_text=entry.get("date", ""),
                file_path=entry.get("path", ""),
            )
            history_list.add_widget(item)

    def _show_error(self, message: str):
        MDSnackbar(
            text=message,
            md_bg_color=self.theme_cls.error_color,
            text_color=(1, 1, 1, 1),
            snackbar_x=dp(16),
            snackbar_y=dp(16),
            size_hint_x=0.9,
        ).open()

    @staticmethod
    def _format_speed(bps: Optional[float]) -> str:
        if not bps:
            return ""
        value = float(bps)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024:
                return f"{value:.1f} {unit}/s"
            value /= 1024
        return f"{value:.1f} GB/s"

    @staticmethod
    def _format_eta(seconds: Optional[float]) -> str:
        if seconds is None or seconds < 0:
            return ""
        total = int(seconds)
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"


if __name__ == "__main__":
    NovaDownloaderApp().run()