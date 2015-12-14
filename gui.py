# -*- coding: utf-8 -*-
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Author(s): Vojtech Trefny <mail@vojtechtrefny.cz>
#
# ---------------------------------------------------------------------------- #

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk

import os

from utils import AppReader

# ---------------------------------------------------------------------------- #

class GUI(object):

    def __init__(self):

        # builder
        self.builder = Gtk.Builder()
        self.builder.add_from_file("ui/main_window.ui")

        # main window
        self.main_window = self.builder.get_object("main_window")
        self.main_window.connect("delete-event", Gtk.main_quit)
        self.applications_list = self.builder.get_object("box_list")
        self.applications_view = self.builder.get_object("box_application")

        self.data = AppReader()

        # radio buttons
        for button_name in ("rec", "inst", "all"):
            button = self.builder.get_object("radiobutton_%s" % button_name)
            button.connect("toggled", self.on_button_toggled, button_name)

        # view filtering
        self.view_type = "rec"
        self.view_filter = self.builder.get_object("treemodelfilter_applications")
        self.view_filter.set_visible_func(self._filter_func)

        # view onclick
        self.treeview_applications = self.builder.get_object("treeview_applications")
        self.treeview_applications.connect("button-press-event", self.on_app_doubleclick)

        # back onclick
        button_back = self.builder.get_object("button_back")
        button_back.connect("clicked", self.on_back_clicked)

        # list of applications
        self.update_app_list()

        # debug information
        self.add_user_debug()

        self.main_window.show_all()

        # hide the applications detail view
        self.applications_view.hide()

    def update_app_list(self):
        apps = self.data.applications
        store = self.builder.get_object("applications_store")

        for app in apps:
            store.append(None, [app, app.recommended, app.installed, self._get_icon(app, 64), self._get_summary(app)])

    def update_app_view(self, app):
        self.applications_list.hide()
        self.applications_view.show()

        label_short = self.builder.get_object("label_short_description")
        label_short.set_markup(self._get_summary(app))

        label_long = self.builder.get_object("label_long_description")
        label_long.set_markup(self._get_description(app))

        button_install = self.builder.get_object("button_install")
        if app.installed:
            button_install.set_label("Already installed")
            button_install.set_sensitive(False)
        else:
            button_install.set_label("Install")
            button_install.set_sensitive(True)

        image_icon = self.builder.get_object("image_icon")
        if os.path.isfile("data/icons/64x64/%s.png" % app.name):
            image_icon.set_from_file("data/icons/64x64/%s.png" % app.name)

        label_debug = self.builder.get_object("label_app_debug")
        label_debug.set_markup(str(app.recommended_debug))

    def add_user_debug(self):
        label_debug = self.builder.get_object("label_main_debug")
        label_debug.set_markup(str(self.data.user_profile))

    def on_back_clicked(self, button):
        self.applications_list.show()
        self.applications_view.hide()

    def on_button_toggled(self, button, name):
        if button.get_active():
            self.view_type = name
        self.view_filter.refilter()

    def on_app_doubleclick(self, treeview, event):
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            path, _column = treeview.get_cursor()
            model = treeview.get_model()

            app = model.get_value(model.get_iter(path), 0)
            self.update_app_view(app)

    def _filter_func(self, model, iter, data):
        if self.view_type == "rec":
            return model[iter][1]
        elif self.view_type == "inst":
            return model[iter][2]
        else:
            return not model[iter][2]

    def _safe_markup(self, string):
        string = string.replace("&", "&amp;")
        return string

    def _get_icon(self, app, size):
        if os.path.isfile("data/icons/%dx%d/%s.png" % (size, size, app.name)):
            icon = Gtk.Image(file="data/icons/%dx%d/%s.png" % (size, size, app.name))
            return icon.get_pixbuf()

    def _get_summary(self, app):
        name = self._safe_markup(app.name)
        summary = self._safe_markup(app.summary)

        return "<b>%s</b>\n<small>%s</small>" % (name, summary)

    def _get_description(self, app):
        return app.desc
