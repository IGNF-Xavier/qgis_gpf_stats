import os

# Force openpyxl's pure-Python XML backend as early as possible in this
# plugin's lifecycle - see exporters/xlsx_exporter.py for why: a stray
# user-site lxml build, ABI-incompatible with the one QGIS bundles, crashes
# the whole process with a native access violation instead of a catchable
# Python exception.
os.environ.setdefault("OPENPYXL_LXML", "False")


def classFactory(iface):  # noqa: N802 - QGIS entry point signature
    from .plugin import Plugin

    return Plugin(iface)
