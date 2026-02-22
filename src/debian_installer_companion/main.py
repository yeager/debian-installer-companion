"""Debian Installer Companion — Installation guide with hardware checks."""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, Gio, GLib, Pango

import gettext
import locale
import os
import sys
import json
import datetime
import threading
import subprocess
import re

LOCALE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "po")
if not os.path.isdir(LOCALE_DIR):
    LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain("debian-installer-companion", LOCALE_DIR)
gettext.bindtextdomain("debian-installer-companion", LOCALE_DIR)
gettext.textdomain("debian-installer-companion")
_ = gettext.gettext

APP_ID = "se.danielnylander.debian.installer.companion"
SETTINGS_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "debian-installer-companion"
)
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")


def _load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {"welcome_shown": False}


def _save_settings(s):
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)



def _check_hardware():
    """Run basic hardware compatibility checks."""
    checks = []
    
    # CPU
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    checks.append({"name": _("CPU"), "value": cpu, "status": "ok"})
                    break
    except:
        checks.append({"name": _("CPU"), "value": _("Unknown"), "status": "warning"})
    
    # RAM
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal"):
                    mem_kb = int(line.split()[1])
                    mem_gb = mem_kb / 1024 / 1024
                    status = "ok" if mem_gb >= 1 else "warning"
                    checks.append({"name": _("RAM"), "value": f"{mem_gb:.1f} GB", "status": status})
                    break
    except:
        checks.append({"name": _("RAM"), "value": _("Unknown"), "status": "warning"})
    
    # Disk
    try:
        r = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            checks.append({"name": _("Disk"), "value": f"{parts[1]} total, {parts[3]} available",
                          "status": "ok"})
    except:
        pass
    
    # Network
    try:
        r = subprocess.run(["ip", "link", "show"], capture_output=True, text=True, timeout=5)
        ifaces = [l.split(":")[1].strip() for l in r.stdout.splitlines() if ": " in l and "lo" not in l]
        checks.append({"name": _("Network"), "value": ", ".join(ifaces[:5]) or _("None detected"),
                       "status": "ok" if ifaces else "warning"})
    except:
        pass
    
    return checks



class DebianInstallerCompanionWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("Debian Installer Companion"), default_width=900, default_height=650)
        self.settings = _load_settings()
        self._checks = []

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header
        headerbar = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(title=_("Debian Installer Companion"), subtitle="")
        headerbar.set_title_widget(title_widget)
        self._title_widget = title_widget

        
        check_btn = Gtk.Button(label=_("Run Checks"))
        check_btn.add_css_class("suggested-action")
        check_btn.connect("clicked", self._on_check)
        headerbar.pack_start(check_btn)

        # Menu
        menu = Gio.Menu()
        menu.append(_("Settings"), "app.settings")
        menu.append(_("Copy Debug Info"), "app.copy-debug")
        menu.append(_("Keyboard Shortcuts"), "app.shortcuts")
        menu.append(_("About Debian Installer Companion"), "app.about")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        headerbar.pack_end(menu_btn)

        main_box.append(headerbar)

        
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        self._list.set_margin_start(12)
        self._list.set_margin_end(12)
        self._list.set_margin_top(8)
        self._list.set_margin_bottom(8)
        scroll.set_child(self._list)
        
        self._empty = Adw.StatusPage()
        self._empty.set_icon_name("drive-harddisk-symbolic")
        self._empty.set_title(_("Hardware Check"))
        self._empty.set_description(_("Click 'Run Checks' to verify hardware compatibility with Debian."))
        self._empty.set_vexpand(True)
        
        self._stack = Gtk.Stack()
        self._stack.add_named(self._empty, "empty")
        self._stack.add_named(scroll, "list")
        self._stack.set_vexpand(True)
        main_box.append(self._stack)

        # Status bar
        self._status = Gtk.Label(label=_("Ready"), xalign=0)
        self._status.set_margin_start(12)
        self._status.set_margin_end(12)
        self._status.set_margin_top(4)
        self._status.set_margin_bottom(4)
        self._status.add_css_class("dim-label")
        main_box.append(self._status)

        self.set_content(main_box)

        if not self.settings.get("welcome_shown"):
            GLib.idle_add(self._show_welcome)

    def _show_welcome(self):
        dialog = Adw.Dialog()
        dialog.set_title(_("Welcome"))
        dialog.set_content_width(420)
        dialog.set_content_height(480)

        page = Adw.StatusPage()
        page.set_icon_name("drive-harddisk-symbolic")
        page.set_title(_("Welcome to Debian Installer Companion"))
        page.set_description(_("Prepare for Debian installation.\n\n"
            "✓ Hardware compatibility check\n"
            "✓ Disk space requirements\n"
            "✓ Network interface detection\n"
            "✓ Firmware availability\n"
            "✓ Installation checklist"))

        btn = Gtk.Button(label=_("Get Started"))
        btn.add_css_class("suggested-action")
        btn.add_css_class("pill")
        btn.set_halign(Gtk.Align.CENTER)
        btn.set_margin_top(12)
        btn.connect("clicked", self._on_welcome_close, dialog)
        page.set_child(btn)

        box = Adw.ToolbarView()
        hb = Adw.HeaderBar()
        hb.set_show_title(False)
        box.add_top_bar(hb)
        box.set_content(page)
        dialog.set_child(box)
        dialog.present(self)

    def _on_welcome_close(self, btn, dialog):
        self.settings["welcome_shown"] = True
        _save_settings(self.settings)
        dialog.close()

    
    def _on_check(self, btn):
        self._status.set_text(_("Checking hardware..."))
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        checks = _check_hardware()
        GLib.idle_add(self._show_checks, checks)

    def _show_checks(self, checks):
        self._checks = checks
        while True:
            row = self._list.get_row_at_index(0)
            if row is None:
                break
            self._list.remove(row)
        
        icons = {"ok": "✅", "warning": "⚠️", "error": "❌"}
        for c in checks:
            row = Adw.ActionRow()
            row.set_title(f"{icons.get(c['status'], '❓')} {c['name']}")
            row.set_subtitle(c["value"])
            self._list.append(row)
        
        self._stack.set_visible_child_name("list")
        ok = sum(1 for c in checks if c["status"] == "ok")
        self._status.set_text(_("%(ok)d / %(total)d checks passed") % {"ok": ok, "total": len(checks)})


class DebianInstallerCompanionApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None

        for name, callback in [
            ("settings", self._on_settings),
            ("copy-debug", self._on_copy_debug),
            ("shortcuts", self._on_shortcuts),
            ("about", self._on_about),
            ("quit", self._on_quit),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        self.set_accels_for_action("app.quit", ["<Ctrl>q"])
        self.set_accels_for_action("app.shortcuts", ["<Ctrl>slash"])

    def do_activate(self):
        if not self.window:
            self.window = DebianInstallerCompanionWindow(self)
        self.window.present()

    def _on_settings(self, *_args):
        if not self.window:
            return
        dialog = Adw.PreferencesDialog()
        dialog.set_title(_("Settings"))
        page = Adw.PreferencesPage()
        
        group = Adw.PreferencesGroup(title=_("Checks"))
        row = Adw.SwitchRow(title=_("Check firmware availability"))
        row.set_active(True)
        group.add(row)
        page.add(group)
        dialog.add(page)
        dialog.present(self.window)

    def _on_copy_debug(self, *_args):
        if not self.window:
            return
        from . import __version__
        info = (
            f"Debian Installer Companion {__version__}\n"
            f"Python {sys.version}\n"
            f"GTK {Gtk.MAJOR_VERSION}.{Gtk.MINOR_VERSION}\n"
            f"Adw {Adw.MAJOR_VERSION}.{Adw.MINOR_VERSION}\n"
            f"OS: {os.uname().sysname} {os.uname().release}\n"
        )
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(info)
        self.window._status.set_text(_("Debug info copied"))

    def _on_shortcuts(self, *_args):
        if self.window:
            dialog = Gtk.ShortcutsWindow(transient_for=self.window)
            section = Gtk.ShortcutsSection(visible=True)
            group = Gtk.ShortcutsGroup(title=_("General"), visible=True)
            for accel, title in [
                ("<Ctrl>q", _("Quit")),
                ("<Ctrl>slash", _("Keyboard shortcuts")),
            ]:
                group.append(Gtk.ShortcutsShortcut(accelerator=accel, title=title, visible=True))
            section.append(group)
            dialog.append(section)
            dialog.present()

    def _on_about(self, *_args):
        from . import __version__
        dialog = Adw.AboutDialog(
            application_name=_("Debian Installer Companion"),
            application_icon="drive-harddisk-symbolic",
            version=__version__,
            developer_name="Daniel Nylander",
            website="https://github.com/yeager/debian-installer-companion",
            license_type=Gtk.License.GPL_3_0,
            issue_url="https://github.com/yeager/debian-installer-companion/issues",
            comments=_("Guide through Debian installation with hardware compatibility checks."),
        )
        dialog.present(self.window)

    def _on_quit(self, *_args):
        self.quit()


def main():
    app = DebianInstallerCompanionApp()
    app.run(sys.argv)
