#!/usr/bin/python

# Ubuntu Tweak - PyGTK based desktop configuration tool
#
# Copyright (C) 2007-2008 TualatriX <tualatrix@gmail.com>
#
# Ubuntu Tweak is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Ubuntu Tweak is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ubuntu Tweak; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA

import pygtk
pyGtk.require("2.0")
from gi.repository import Gdk
from gi.repository import Gtk
import os
from gi.repository import GConf
import gettext
import gobject

from ubuntutweak.modules  import TweakModule
from ubuntutweak.ui import KeyGrabber, KeyModifier, CellRendererButton
from ubuntutweak.utils import icon
from compiz import CompizPlugin

(
    COLUMN_ID,
    COLUMN_LOGO,
    COLUMN_TITLE,
    COLUMN_ICON,
    COLUMN_COMMAND,
    COLUMN_KEY,
    COLUMN_EDITABLE,
) = range(7)

class Shortcuts(TweakModule):
    __title__  = _("Shortcut Commands")
    __desc__  = _("By configuring keyboard shortcuts, you can access your favourite applications instantly.\n"
                  "Enter the command to run the application and choose a shortcut key combination.")
    __icon__ = 'preferences-desktop-keyboard-shortcuts'
    __category__ = 'personal'
    __desktop__ = ['gnome', 'une']

    def __init__(self):
        TweakModule.__init__(self)

        if not CompizPlugin.get_plugin_active('commands'):
            CompizPlugin.set_plugin_active('commands', True)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.add_start(sw)

        treeview = self.create_treeview()
        sw.add(treeview)
    
    def create_treeview(self):
        treeview = Gtk.TreeView()

        self.model = self.__create_model()

        treeview.set_model(self.model)

        self.__add_columns(treeview)

        return treeview

    def __create_model(self):
        model = Gtk.ListStore(
                    gobject.TYPE_INT,
                    GdkPixbuf.Pixbuf,
                    gobject.TYPE_STRING,
                    GdkPixbuf.Pixbuf,
                    gobject.TYPE_STRING,
                    gobject.TYPE_STRING,
                    gobject.TYPE_BOOLEAN,
                )

        client = GConf.Client.get_default()
        logo = icon.get_from_name('gnome-terminal')

        for id in range(12):
            iter = model.append()
            id = id + 1

            title = _("Command %d") % id
            command = client.get_string("/apps/metacity/keybinding_commands/command_%d" % id)
            key = client.get_string("/apps/metacity/global_keybindings/run_command_%d" % id)

            if not command:
                command = _("None")

            pixbuf = icon.get_from_name(command)

            if key == "disabled":
                key = _("disabled")

            model.set(iter,
                    COLUMN_ID, id,
                    COLUMN_LOGO, logo,
                    COLUMN_TITLE, title,
                    COLUMN_ICON, pixbuf,
                    COLUMN_COMMAND, command,
                    COLUMN_KEY, key,
                    COLUMN_EDITABLE, True)

        return model

    def __add_columns(self, treeview):
        model = treeview.get_model()

        column = Gtk.TreeViewColumn(_("ID"))

        renderer = Gtk.CellRendererPixbuf()
        column.pack_start(renderer, False)
        column.set_attributes(renderer, pixbuf = COLUMN_LOGO)

        renderer = Gtk.CellRendererText()
        column.pack_start(renderer, True)
        column.set_attributes(renderer, text = COLUMN_TITLE)
        treeview.append_column(column)

        column = Gtk.TreeViewColumn(_("Command"))

        renderer = Gtk.CellRendererPixbuf()
        column.pack_start(renderer, False)
        column.set_attributes(renderer, pixbuf = COLUMN_ICON)

        renderer = Gtk.CellRendererText()
        renderer.connect("edited", self.on_cell_edited, model)
        column.pack_start(renderer, True)
        column.set_attributes(renderer, text = COLUMN_COMMAND, editable = COLUMN_EDITABLE)
        treeview.append_column(column)

        column = Gtk.TreeViewColumn(_("Key"))

        renderer = Gtk.CellRendererText()
        renderer.connect("editing-started", self.on_editing_started)
        renderer.connect("edited", self.on_cell_edited, model)
        column.pack_start(renderer, True)
        column.set_attributes(renderer, text=COLUMN_KEY, editable=COLUMN_EDITABLE)
        column.set_resizable(True)
        treeview.append_column(column)

        renderer = CellRendererButton(_("Clean"))
        renderer.connect("clicked", self.on_clean_clicked)
        column.pack_end(renderer, False)

    def on_clean_clicked(self, cell, path):
        iter = self.model.get_iter_from_string(path)
        id = self.model.get_value(iter, COLUMN_ID)
        self.model.set_value(iter, COLUMN_KEY, _("disabled"))
        client = GConf.Client.get_default()
        client.set_string("/apps/metacity/global_keybindings/run_command_%d" % id, "disabled")

    def on_got_key(self, widget, key, mods, cell):
        new = Gtk.accelerator_name (key, mods)
        for mod in KeyModifier:
            if "%s_L" % mod in new:
                new = new.replace ("%s_L" % mod, "<%s>" % mod)
            if "%s_R" % mod in new:
                new = new.replace ("%s_R" % mod, "<%s>" % mod)

        widget.destroy()

        client = GConf.Client.get_default()
        column = cell.get_data("id")
        iter = self.model.get_iter_from_string(cell.get_data("path_string"))

        id = self.model.get_value(iter, COLUMN_ID)

        client.set_string("/apps/metacity/global_keybindings/run_command_%d" % id, new)
        self.model.set_value(iter, COLUMN_KEY, new)

    def on_editing_started(self, cell, editable, path):
        grabber = KeyGrabber(self.get_toplevel(), label = "Grab key combination")
        cell.set_data("path_string", path)
        grabber.hide()
        grabber.set_no_show_all(True)
        grabber.connect('changed', self.on_got_key, cell)
        grabber.begin_key_grab(None)

    def on_cell_edited(self, cell, path_string, new_text, model):
        iter = model.get_iter_from_string(path_string)

        client = GConf.Client.get_default()
        column = cell.get_data("id")

        id = model.get_value(iter, COLUMN_ID)
        old = model.get_value(iter, COLUMN_COMMAND)

        if old != new_text:
            client.set_string("/apps/metacity/keybinding_commands/command_%d" % id, new_text)
            if new_text:
                pixbuf = icon.get_from_name(new_text)

                model.set_value(iter, COLUMN_ICON, pixbuf)
                model.set_value(iter, COLUMN_COMMAND, new_text)
            else:
                model.set_value(iter, COLUMN_ICON, None)
                model.set_value(iter, COLUMN_COMMAND, _("None"))
