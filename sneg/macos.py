"""CoreGraphics geometry through the system C API; no PyObjC or compiler needed."""
import ctypes as c
import plistlib


def window_info():
    cg = c.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
    cf = c.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    cg.CGWindowListCopyWindowInfo.argtypes = [c.c_uint32, c.c_uint32]
    cg.CGWindowListCopyWindowInfo.restype = c.c_void_p
    cf.CFPropertyListCreateData.argtypes = [c.c_void_p,c.c_void_p,c.c_long,c.c_ulong,c.POINTER(c.c_void_p)]
    cf.CFPropertyListCreateData.restype = c.c_void_p
    cf.CFDataGetLength.argtypes = [c.c_void_p]
    cf.CFDataGetLength.restype = c.c_long
    cf.CFDataGetBytePtr.argtypes = [c.c_void_p]
    cf.CFDataGetBytePtr.restype = c.c_void_p
    cf.CFRelease.argtypes = [c.c_void_p]
    cf.CFRelease.restype = None
    rows = cg.CGWindowListCopyWindowInfo(1 | 16, 0)
    if not rows:
        raise RuntimeError('macOS не предоставила список окон')
    data = None
    error = c.c_void_p()
    try:
        data = cf.CFPropertyListCreateData(None, rows, 100, 0, c.byref(error))
        if not data:
            raise RuntimeError('Не удалось прочитать геометрию окон macOS')
        return plistlib.loads(c.string_at(cf.CFDataGetBytePtr(data),cf.CFDataGetLength(data)))
    finally:
        if data: cf.CFRelease(data)
        if error.value: cf.CFRelease(error)
        cf.CFRelease(rows)
