"""Layout GUI (PySide6). All GUI code lives in this package.

    app.py          QApplication, the terminal input hook, display check
    main_window.py  window: layout canvas, right-side visibility panel, status bar
    canvas.py       zoomable layout view (QGraphicsView)
    layout_data.py  database -> drawing data; no Qt, so it is testable alone
"""
