def classFactory(iface):  # noqa: N802 - QGIS entry point signature
    from .plugin import Plugin

    return Plugin(iface)
