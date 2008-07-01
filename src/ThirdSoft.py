#!/usr/bin/env python

# Ubuntu Tweak - PyGTK based desktop configure tool
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
pygtk.require("2.0")
import gtk
import gtk.glade
import os
import dbus
import time
import thread
import subprocess
import gobject
import gettext
import apt_pkg

from Constants import *
from Factory import Factory
from PolicyKit import PolkitButton, DbusProxy
from Widgets import ListPack, TweakPage, Colleague, Mediator
from aptsources.sourceslist import SourceEntry, SourcesList
from PolicyKit import PolkitButton

gettext.install(App, unicode = True)

(
    COLUMN_ENABLED,
    COLUMN_URL,
    COLUMN_COMPS,
    COLUMN_NAME,
    COLUMN_COMMENT,
) = range(5)

(
    ENTRY_URL,
    ENTRY_COMPS,
    ENTRY_NAME,
    ENTRY_COMMENT,
) = range(4)

SOURCES_DATA = [
    ['http://ppa.launchpad.net/awn-core/ubuntu', ['main'], 'AWN', _('Fully customisable dock-like window navigator')],
    ['http://ppa.launchpad.net/stemp/ubuntu', ['main'], 'Midori', _('Webkit based lightweight web browser')],
    ['http://ppa.launchpad.net/fta/ubuntu', ['main'], 'Firefox', _('Development version of firefox 3.0/3.1, 4.0')],
    ['http://ppa.launchpad.net/compiz/ubuntu', ['main'], 'Compiz Fusion', _('Development version of Compiz Fusion')],
    ['http://ppa.launchpad.net/do-core/ubuntu', ['main'], 'GNOME Do', _('Do things as quickly as possible')],
    ['http://ppa.launchpad.net/banshee-team/ubuntu', ['main'], 'Banshee', _('Audio Management and Playback application')],
    ['http://ppa.launchpad.net/googlegadgets/ubuntu', ['main'], 'Google gadgets', _('Platform for running Google Gadgets on Linux')],
    ['http://ppa.launchpad.net/lidaobing/ubuntu', ['main'], 'chmsee', _('A chm file viewer written in GTK+')],
    ['http://ppa.launchpad.net/kubuntu-members-kde4/ubuntu', ['main'], 'KDE 4', _('K Desktop Environment 4.1')],
    ['http://ppa.launchpad.net/tualatrix/ubuntu', ['main'], 'Ubuntu Tweak', _('Tweak ubuntu to what you like')],
    ['http://wine.budgetdedicated.com/apt', ['main'], 'Wine', _('A compatibility layer for running Windows programs')],
    ['http://ppa.launchpad.net/lxde/ubuntu', ['main'], 'LXDE', _('Lightweight X11 Desktop Environment:GPicView, PCManFM')],
]

class UpdateCacheDialog:
    """This class is modified from Software-Properties"""
    def __init__(self, parent):
        self.parent = parent

        self.dialog = gtk.MessageDialog(parent, buttons = gtk.BUTTONS_YES_NO)
        self.dialog.set_markup(_("<b><big>The information about available software is out-of-date</big></b>\n\nTo install software and updates from newly added or changed sources, you have to reload the information about available software.\n\nYou need a working internet connection to continue."))

    def update_cache(self, window_id, lock):
        """start synaptic to update the package cache"""
        try:
            apt_pkg.PkgSystemUnLock()
        except SystemError:
            pass
        cmd = []
        if os.getuid() != 0:
            cmd = ["/usr/bin/gksu",
                   "--desktop", "/usr/share/applications/synaptic.desktop",
                   "--"]
        
        cmd += ["/usr/sbin/synaptic", "--hide-main-window",
               "--non-interactive",
               "--parent-window-id", "%s" % (window_id),
               "--update-at-startup"]
        subprocess.call(cmd)
        lock.release()

    def run(self):
        """run the dialog, and if reload was pressed run synaptic"""
        res = self.dialog.run()
        self.dialog.hide()
        if res == gtk.RESPONSE_YES:
            self.parent.set_sensitive(False)
            lock = thread.allocate_lock()
            lock.acquire()
            t = thread.start_new_thread(self.update_cache,
                                       (self.parent.window.xid, lock))
            while lock.locked():
                while gtk.events_pending():
                    gtk.main_iteration()
                    time.sleep(0.05)
            self.parent.set_sensitive(True)
        return res

class SourcesView(gtk.TreeView, Colleague):
    def __init__(self, mediator):
        gtk.TreeView.__init__(self)
        Colleague.__init__(self, mediator)

        self.list = SourcesList()
        self.proxy = DbusProxy()
        self.model = self.__create_model()
        self.set_model(self.model)
        self.__add_column()

        self.update_model()

    def __create_model(self):
        model = gtk.ListStore(
                gobject.TYPE_BOOLEAN,
                gobject.TYPE_STRING,
                gobject.TYPE_STRING,
                gobject.TYPE_STRING,
                gobject.TYPE_STRING)

        return model

    def __add_column(self):
        renderer = gtk.CellRendererToggle()
        renderer.connect('toggled', self.on_enable_toggled)
        column = gtk.TreeViewColumn(' ', renderer, active = COLUMN_ENABLED)
        self.append_column(column)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Application', renderer, markup = COLUMN_COMMENT)
        self.append_column(column)

    def update_model(self):
        for entry in SOURCES_DATA:
            enabled = False
            url = entry[ENTRY_URL]
            comps = entry[ENTRY_COMPS]
            name = entry[ENTRY_NAME]
            comment = entry[ENTRY_COMMENT]
            comment = "<b>%s</b>: %s" % (name, comment)

            for source in self.list:
                if url in source.str() and source.type == 'deb':
                    enabled = not source.disabled

            self.model.append((
                enabled,
                url,
                comps,
                name,
                comment,
                ))

    def on_enable_toggled(self, cell, path):
        iter = self.model.get_iter((int(path),))

        enabled = self.model.get_value(iter, COLUMN_ENABLED)
        url = self.model.get_value(iter, COLUMN_URL)
        name = self.model.get_value(iter, COLUMN_NAME)

        result = self.proxy.proxy.SetSourcesList(url, name, not enabled, dbus_interface = self.proxy.INTERFACE)

        if result == 'enabled':
            self.model.set(iter, COLUMN_ENABLED, True)
        else:
            self.model.set(iter, COLUMN_ENABLED, False)
            
        self.state_changed(cell)
    
    def set_sourceslist_state(self, state):
        self.proxy.proxy.SetListState(state, dbus_interface = self.proxy.INTERFACE)

class ThirdSoft(TweakPage, Mediator):
    def __init__(self, parent = None):
        TweakPage.__init__(self)

        self.set_title(_("Third-Party Softwares Sources"))
        self.set_description(_("You can always follow the latest version of a application.\nJust enable the application what you want."))

        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.pack_start(sw)

        self.treeview = SourcesView(self)
        self.treeview.set_sensitive(False)
        self.treeview.set_rules_hint(True)
        sw.add(self.treeview)

        hbox = gtk.HBox(False, 0)
        self.pack_end(hbox, False, False, 5)

        un_lock = PolkitButton()
        un_lock.connect("clicked", self.on_polkit_action)
        hbox.pack_end(un_lock, False, False, 5)

        self.refresh_button = gtk.Button(stock = gtk.STOCK_REFRESH)
        self.refresh_button.set_sensitive(False)
        self.refresh_button.connect("clicked", self.on_refresh_button_clicked)
        hbox.pack_end(self.refresh_button, False, False, 5)

    def on_polkit_action(self, widget):
        if widget.action == 1:
            self.treeview.set_sensitive(True)
            
    def colleague_changed(self):
        self.refresh_button.set_sensitive(True)
    
    def on_refresh_button_clicked(self, widget):
        dialog = UpdateCacheDialog(widget.get_toplevel())
        res = dialog.run()
        self.treeview.set_sourceslist_state('normal')
        widget.set_sensitive(False)

if __name__ == "__main__":
    from Utility import Test
    gtk.gdk.threads_init()
    Test(ThirdSoft)