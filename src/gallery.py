#!/usr/bin/env python

import os
import gtk
import gobject

from imagefile import GTKIconImage
from filescanner import FileScanner
from filemanager import FileManager

from thumbnail import DirectoryThumbnail

from cache import Cache, cached
from worker import Worker

class GalleryItem:
    def __init__(self, item, size):
        self.item = item
        self.size = size

    def initial_data(self):
        pass

    def final_thumbnail(self):
        pass

    def on_selected(self, gallery):
        pass

class ImageItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)

    def initial_data(self):
        unknown_icon = GTKIconImage(gtk.STOCK_MISSING_IMAGE, self.size)
        return (unknown_icon.get_pixbuf(), 
                self.item.get_basename(),
                self.item.get_filename())

    @cached()
    def final_thumbnail(self):
        width, height = self.item.get_dimensions_to_fit(self.size, self.size)
        return self.item.get_pixbuf_at_size(width, height)

    def on_selected(self, gallery):
        gallery.on_image_selected(self.item)

class DirectoryItem(GalleryItem):
    def __init__(self, item, size):
        GalleryItem.__init__(self, item, size)
        self.thumbnail = DirectoryThumbnail(item)

    def initial_data(self):
        unknown_icon = GTKIconImage(gtk.STOCK_MISSING_IMAGE, self.size)
        return (self.thumbnail.get_mixed_thumbnail(unknown_icon, self.size),
                os.path.basename(self.item),
                self.item)

    def final_thumbnail(self):
        return self.thumbnail.get_pixbuf_at_size(self.size, self.size)

    def on_selected(self, gallery):
        gallery.on_dir_selected(self.item)

class Gallery:
    liststore_cache = Cache(shared=True, 
                            top_cache=FileScanner.cache)

    def __init__(self, title, parent, dirname, last_targets, callback,
                       dir_selector = False,
                       columns = 3,
                       thumb_size = 256,
                       quick_thumb_size = 48,
                       width = 600,
                       height = 600,
                       quick_width = 300):
        self.callback = callback
        self.dir_selector = dir_selector
        self.thumb_size = thumb_size

        self.window = gtk.Window()
        self.window.set_position(gtk.WIN_POS_CENTER)
        self.window.set_resizable(False)
        self.window.set_modal(True)
        self.window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)
        self.window.set_transient_for(parent)
        
        self.window.connect("key_press_event", self.on_key_press_event)

        # Main HBox of the window
        hbox = gtk.HBox(False, 5)
        self.window.add(hbox)

        # Left pane (quick access)
        vbox = gtk.VBox(False, 5)
        hbox.pack_start(vbox, True, True, 0)

        store = gtk.ListStore(gtk.gdk.Pixbuf, str, str)

        store.append((GTKIconImage(gtk.STOCK_HARDDISK, quick_thumb_size).get_pixbuf(), 
                      "File System", "/"))

        home = os.path.realpath(os.path.expanduser("~"))
        store.append((GTKIconImage(gtk.STOCK_HOME, quick_thumb_size).get_pixbuf(), 
                      "Home", home))

        downloads = os.path.join(home, "Downloads")
        thumb = DirectoryThumbnail(downloads) 
        store.append((thumb.get_pixbuf_at_size(quick_thumb_size, 
                                               quick_thumb_size), 
                      "Downloads", downloads))

        pictures = os.path.join(home, "Pictures")
        thumb = DirectoryThumbnail(pictures) 
        store.append((thumb.get_pixbuf_at_size(quick_thumb_size, 
                                               quick_thumb_size), 
                      "Pictures", pictures))

        for directory in last_targets:
            thumb = DirectoryThumbnail(directory) 
            store.append((thumb.get_pixbuf_at_size(quick_thumb_size, 
                                                   quick_thumb_size), 
                          os.path.basename(directory),
                          directory))

        treeview = gtk.TreeView(store)
        treeview.set_headers_visible(False)
        treeview.connect_after("cursor-changed", self.on_cursor_changed)

        renderer = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", renderer, pixbuf=0)
        treeview.append_column(column)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Path", renderer, text=1)
        treeview.append_column(column)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled.add_with_viewport(treeview)
        scrolled.set_size_request(quick_width, height)

        vbox.pack_start(scrolled, True, True, 0)

        # Right pane (location, iconview)
        vbox = gtk.VBox(False, 5)
        hbox.pack_start(vbox, True, True, 0)

        # Toolbar
        toolbar = gtk.Toolbar()
        toolbar.set_style(gtk.TOOLBAR_BOTH_HORIZ)

        vbox.pack_start(toolbar, False, False, 0)

        button = gtk.ToolButton(gtk.STOCK_GO_UP)
        button.set_label("Go up")
        button.connect("clicked", self.on_go_up)
        button.set_is_important(True)
        toolbar.insert(button, -1)
        self.go_up = button

        button = gtk.ToolButton(gtk.STOCK_DIRECTORY)
        button.set_label("New folder")
        button.connect("clicked", self.on_new_folder)
        button.set_is_important(True)
        toolbar.insert(button, -1)

        # "Location"/"Filter" bar
        location_bar = gtk.HBox(False, 5)
        vbox.pack_start(location_bar, False, False, 0)

        label = gtk.Label()
        label.set_text("Location:")
        location_bar.pack_start(label, False, False, 0)

        self.location_entry = gtk.Entry()
        self.location_entry.connect("activate", self.on_location_entry_activate)
        location_bar.pack_start(self.location_entry, True, True, 0)

        self.filter_entry = gtk.Entry()
        self.filter_entry.connect("activate", self.on_filter_entry_activate)
        location_bar.pack_end(self.filter_entry, False, False, 0)

        label = gtk.Label()
        label.set_text("Filter:")
        location_bar.pack_end(label, False, False, 0)

        # Iconview
        self.iconview = gtk.IconView()
        self.iconview.set_pixbuf_column(0)
        self.iconview.set_text_column(1)
        self.iconview.set_tooltip_column(2)
        self.iconview.set_selection_mode(gtk.SELECTION_SINGLE)
        self.iconview.set_item_width(self.thumb_size)
        self.iconview.set_columns(columns)

        self.iconview.connect("selection-changed", self.on_selection_changed)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled.add_with_viewport(self.iconview)
        scrolled.set_size_request(int((thumb_size * 1.06) * columns), height)

        vbox.pack_start(scrolled, True, True, 0)

        # Buttonbar
        buttonbar = gtk.HBox(False, 0)

        button = gtk.Button(stock=gtk.STOCK_OK)
        button.set_relief(gtk.RELIEF_NONE)
        button.connect("clicked", self.on_ok_clicked)
        buttonbar.pack_end(button, False, False, 5)

        button = gtk.Button(stock=gtk.STOCK_CANCEL)
        button.set_relief(gtk.RELIEF_NONE)
        button.connect("clicked", self.on_cancel_clicked)
        buttonbar.pack_end(button, False, False, 0)

        vbox.pack_start(buttonbar, False, False, 5)

        # Enable icons in buttons:
        settings = gtk.settings_get_default()
        settings.props.gtk_button_images = True

        # Data initialization:
        self.loader = Worker()
        self.loader.start()

        self.curdir = os.path.realpath(os.path.expanduser(dirname))
        self.last_filter = ""
        self.items = []

        self.update_model()
        
    def run(self):
        self.window.show_all()
        self.filter_entry.grab_focus()
    
    def get_items_for_dir(self, directory, filter_):
        items = []

        # Obtain the directories first:
        scanner = FileScanner()

        for dir_ in scanner.get_dirs_from_dir(directory):
            if filter_ and not filter_.lower() in dir_.lower():
                continue
            items.append(DirectoryItem(dir_, self.thumb_size/2))
    
        # Now the files:
        files = scanner.get_files_from_dir(directory)
        
        file_manager = FileManager(on_list_modified=lambda: None)
        file_manager.set_files(files)
        file_manager.sort_by_date(True)
        file_manager.go_first()

        for _ in range(file_manager.get_list_length()):
            current_file = file_manager.get_current_file()
            if not filter_ or filter_.lower() in current_file.get_basename().lower():
                items.append(ImageItem(current_file, self.thumb_size/2))
            file_manager.go_forward(1)

        return items

    @cached(liststore_cache)
    def build_store(self, directory, filter_):
        liststore = gtk.ListStore(gtk.gdk.Pixbuf, str, str)

        # Retrieve the items for this dir:
        items = self.get_items_for_dir(directory, filter_)

        # And fill the store:
        for item in items:
            # Load the inital data:
            liststore.append(item.initial_data())

        return items, liststore

    def update_model(self, filter_=""):
        self.loader.clear()

        items, liststore = self.build_store(self.curdir, filter_)

        for index, item in enumerate(items):
            # Schedule an update on this item:
            self.loader.push((self.update_item_thumbnail, (liststore, index, item)))

        # Update the items list:
        self.items = items
        # Associate the new liststore to the iconview:
        self.iconview.set_model(liststore)
        # Update the curdir entry widget:
        self.location_entry.set_text(self.curdir)

    # This is done in a separate thread:
    def update_item_thumbnail(self, liststore, index, item):
        pixbuf = item.final_thumbnail()
        return (self.update_store_entry, (liststore, index, pixbuf))

    # This is requested to be done by the main thread:
    def update_store_entry(self, liststore, index, pixbuf):
        iter_ = liststore.get_iter((index,))
        liststore.set_value(iter_, 0, pixbuf)

    def on_key_press_event(self, widget, event, data=None):
        key_name = gtk.gdk.keyval_name(event.keyval)
        #print "gallery - key pressed:", key_name

        bindings = {
            "Escape" : self.close,
            "Up" : lambda: self.on_go_up(None),
        }

        if key_name in bindings:
            bindings[key_name]()
            return True

    def on_cursor_changed(self, treeview):
        selection = treeview.get_selection()
        model, iter_ = selection.get_selected()

        if iter_:
            directory = model.get_value(iter_, 2)
            self.on_dir_selected(directory)

    def on_go_up(self, widget):
        self.on_dir_selected(os.path.split(self.curdir)[0])

    def on_go_home(self, widget):
        self.on_dir_selected(os.path.realpath(os.path.expanduser('~')))

    def on_new_folder(self, widget):
        def on_entry(folder):
            manager = FileManager()
            manager.create_directory(os.path.join(self.curdir, folder))
            self.update_model()

        dialog = NewFolderDialog(self.window, on_entry)
        dialog.run()

    def on_location_entry_activate(self, entry):
        directory = entry.get_text()
        if os.path.isdir(directory):
            self.on_dir_selected(directory)
        else:
            entry.set_text(self.curdir)

    def on_filter_entry_activate(self, entry):
        if (not entry.get_text() and 
            not self.last_filter and 
            self.dir_selector):
            self.callback(self.curdir)
            self.close()
            return

        # Restrict the entries to those containing the filter:
        self.update_model(entry.get_text())
        self.last_filter = entry.get_text()

        # If only one item matches, simulate it's been selected:
        if len(self.items) == 1:
            self.items[0].on_selected(self)

    def on_selection_changed(self, iconview):
        selected = iconview.get_selected_items()

        if not selected:
            return

        index = selected[0][0]
        item = self.items[index]
        iconview.unselect_all()

        item.on_selected(self)
        
    def on_image_selected(self, item):
        self.callback(item.get_filename())
        self.close()

    def on_dir_selected(self, item):
        scanner = FileScanner()
        dirs = scanner.get_dirs_from_dir(item)

        if self.dir_selector and not dirs:
            self.callback(item)
            self.close()
            return

        self.curdir = item
        self.go_up.set_sensitive(self.curdir != "/")
        self.update_model()
        self.last_filter = ""
        self.filter_entry.set_text("")
        self.filter_entry.grab_focus()

    def on_ok_clicked(self, button):
        if not self.dir_selector:
            return
        self.callback(self.curdir)
        self.close()
        
    def on_cancel_clicked(self, button):
        self.close()

    def close(self):
        self.loader.stop()
        self.loader.join()
        # This is to avoid invoking self.window.destroy() directly, it
        # was causing a SIGSEGV after the on_cursor_changed handler ran
        # (https://mail.gnome.org/archives/gtk-app-devel-list/2004-September/msg00230.html)
        gobject.idle_add(lambda window: window.destroy(), self.window)
        
class NewFolderDialog:
    def __init__(self, parent, callback):
        self.callback = callback

        self.window = gtk.Dialog(title="New folder", 
                                 parent=parent, 
                                 flags=gtk.DIALOG_MODAL)

        label = gtk.Label()
        label.set_text("Enter new folder name:")
        self.window.action_area.pack_start(label, True, True, 5)

        self.entry = gtk.Entry()
        self.entry.connect("activate", self.on_entry_activate)
        self.window.action_area.pack_start(self.entry, True, True, 5)

    def on_entry_activate(self, entry):
        text = entry.get_text()
        if text:
            gtk.Widget.destroy(self.window)
            self.callback(text)

    def run(self):
        self.window.show_all()