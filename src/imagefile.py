import os
import time
import shutil
import hashlib

import gtk

from cache import Cache, cached
from utils import trash, untrash, external_open

class ImageDimensions:
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def get_width(self):
        return self.width

    def get_height(self):
        return self.height

    def __str__(self):
        return "%dx%d" % (self.width, self.height)

class Size:
    def __init__(self, size):
        self.size = size

    def __str__(self):
        if self.size < 1024:
            return "%d bytes" % self.size
        elif self.size < (1024*1024):
            return "%.2f Kb" % (self.size/1024)
        else:
            return "%.2f Mb" % (self.size/(1024*1024))

class Datetime:
    def __init__(self, datetime):
        self.datetime = datetime

    def __lt__(self, other):
        return self.datetime < other.datetime

    def __str__(self):
        return time.strftime("%a %b %d %Y %X", time.localtime(self.datetime))

class File:
    def __init__(self, filename):
        self.filename = filename

    def get_filename(self):
        return self.filename

    def get_dirname(self):
        return os.path.dirname(self.filename)

    def get_basename(self):
        return os.path.basename(self.filename)

    def get_filesize(self):
        stat = os.stat(self.filename)
        size = stat.st_size
        return Size(size)

    @cached()
    def get_sha1(self):
        with open(self.filename, "r") as input_:
            return hashlib.sha1(input_.read()).hexdigest()

    def get_atime(self):
        return Datetime(os.stat(self.filename).st_atime)

    def get_mtime(self):
        return Datetime(os.stat(self.filename).st_mtime)

    def get_ctime(self):
        return Datetime(os.stat(self.filename).st_ctime)

    def __hash__(self):
        return hash(self.filename)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.filename == other
        else:
            raise Exception("Can't compare File to " + repr(other))

    def rename(self, new_name):
        shutil.move(self.filename, new_name)
        self.filename = new_name

    def trash(self):
        trash(self.filename)

    def untrash(self):
        untrash(self.filename)

    def external_open(self):
        external_open(self.filename)

    def embedded_open(self, xid):
        pass

class ImageFile(File):
    description = "image"
    pixbuf_cache = Cache(10)

    def __init__(self, filename):
        File.__init__(self, filename)
        self.rotation = 0
        self.flip_h = False
        self.flip_v = False

    def draw(self, widget, width, height):
        widget.set_from_pixbuf(self.get_pixbuf_at_size(width, height))

    @cached(pixbuf_cache)
    def get_pixbuf(self):
        return gtk.gdk.pixbuf_new_from_file(self.get_filename())

    def toggle_flip(self, horizontal):
        if horizontal:
            self.flip_h = not self.flip_h
        else:
            self.flip_v = not self.flip_v

    def rotate(self, clockwise):
        angle = (+90 if clockwise else -90)
        self.rotation = (self.rotation + angle) % 360

    def get_pixbuf_at_size(self, width, height):
        angle_constants = {0: gtk.gdk.PIXBUF_ROTATE_NONE,
                           90: gtk.gdk.PIXBUF_ROTATE_CLOCKWISE,
                           180: gtk.gdk.PIXBUF_ROTATE_UPSIDEDOWN,
                           270: gtk.gdk.PIXBUF_ROTATE_COUNTERCLOCKWISE}
    
        pixbuf = self.get_pixbuf()
        scaled = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        flipped = scaled.flip(True) if self.flip_h else scaled
        flipped = flipped.flip(False) if self.flip_v else flipped
        rotated = flipped.rotate_simple(angle_constants[self.rotation])

        return rotated

    @cached()
    def get_dimensions(self):
        return ImageDimensions(self.get_pixbuf().get_width(), 
                               self.get_pixbuf().get_height())

    def get_empty_pixbuf(self):
        pixbuf = gtk.gdk.Pixbuf(colorspace=gtk.gdk.COLORSPACE_RGB, 
                                has_alpha=False, 
                                bits_per_sample=8, 
                                width=1, 
                                height=1)
        pixbuf.fill(0)
        return pixbuf
