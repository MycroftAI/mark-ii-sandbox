import sys
import gdb

# Update module path.
dir_ = '/gnu/store/fp9b5s3ir3jna4xafqwhrq6i70jid2ry-glib-2.70.2/share/glib-2.0/gdb'
if not dir_ in sys.path:
    sys.path.insert(0, dir_)

from gobject_gdb import register
register (gdb.current_objfile ())
