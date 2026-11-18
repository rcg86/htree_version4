"""DRC Violations: the table of what the last check_drc found.

It opens under the layout when check_drc has run. One row per violation, in
the order of the report: its check, its rule (tech | custom; of an open
signal | power), layer, nets, box and the line of the report. A click on a
row (or the arrow keys) lets the violation be debugged: only its nets are
shown (show_only, run as if typed), its shapes are selected and the layout
zooms to its box. Show All runs show_only -show_all.

The table is the run as check_drc left it: after a fix, check_drc again.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDockWidget,
                               QHBoxLayout, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from core import drc, netlist, objects
from core.commands.show_only import net_handles

COLUMNS = ["#", "Check", "Rule", "Layer", "Nets", "Box", "Violation"]
NUMBER, NETS, TEXT = 0, 4, 6
ALL = "All"


def debug_objects(db, v):
    """The objects show_only is given for a violation: its nets. A shape on
    no net (core/drc.py collect: '<inst>/<pin>' of a pin nothing is connected
    to, '<inst>/strap<n>' of a strap not routed yet) gives its instance, and
    so does a pin the nets do not draw (a power pin: no pin of the netlist).
    A net or instance that is gone since the check gives nothing."""
    nets = net_handles(db)
    by_net = netlist.by_net(db)
    drawn = {pin for name in v.nets for pin in by_net.get(name, [])}
    found = [nets[name] for name in v.nets if name in nets]
    insts = [name.rpartition("/")[0] for name in v.nets if name not in nets]
    for handle in v.handles:
        inst, _, pin = handle.partition(":")[2].rpartition("/")
        if handle.startswith("pin:") and (inst, pin) not in drawn:
            insts.append(inst)
    found += [f"inst:{inst}" for inst in insts if objects.exists(db, f"inst:{inst}")]
    return list(dict.fromkeys(found))


class DrcTable(QDockWidget):
    def __init__(self, window):
        super().__init__("DRC Violations", window)
        self.setObjectName("drc_table")
        self.win = window
        self.report = None                   # the drc.Report listed

        panel = QWidget()
        vbox = QVBoxLayout(panel)
        top = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setStyleSheet("font-weight: bold;")
        top.addWidget(self.summary, 1)
        self.filter_box = QComboBox()
        self.filter_box.setToolTip("List the violations of one check only")
        self.filter_box.currentIndexChanged.connect(lambda _: self._filter())
        top.addWidget(self.filter_box)
        self.all_button = QPushButton("Show All")
        self.all_button.setToolTip("Show every instance and all net routing again "
                                   "(show_only -show_all)")
        self.all_button.setFocusPolicy(Qt.NoFocus)
        self.all_button.clicked.connect(lambda: self.win.run_command("show_only -show_all"))
        top.addWidget(self.all_button)
        vbox.addLayout(top)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setToolTip("Click a violation: only its nets are shown (show_only), its "
                              "shapes selected, the layout zooms to its box")
        # A click always shows its violation (again too, after Show All); the arrow
        # keys show the one they move to.
        self.table.cellClicked.connect(lambda row, _: self._show(row))
        self.table.currentCellChanged.connect(self._moved)
        vbox.addWidget(self.table)
        self.setWidget(panel)

    def set_report(self, report):
        """List a check_drc run (drc.Report); None: no run, an empty table."""
        self.report = report
        rows = report.rows if report is not None else []
        table = self.table
        table.blockSignals(True)
        table.setSortingEnabled(False)
        table.clearSelection()
        table.setRowCount(len(rows))
        for k, (title, v) in enumerate(rows):
            number = QTableWidgetItem()
            number.setData(Qt.DisplayRole, k + 1)         # a number: sorts as one
            number.setData(Qt.UserRole, k)
            table.setItem(k, NUMBER, number)
            words = [v.check, v.source or "-", v.layer or "-", ", ".join(v.nets),
                     drc.box_text(v.bbox), v.text]
            for col, text in enumerate(words, start=1):
                item = QTableWidgetItem(text)
                if col in (NETS, TEXT):
                    item.setToolTip(text)
                table.setItem(k, col, item)
            table.item(k, 1).setToolTip(title)
        table.setCurrentCell(-1, -1)
        table.setSortingEnabled(True)
        table.sortByColumn(NUMBER, Qt.AscendingOrder)
        table.resizeColumnsToContents()
        table.blockSignals(False)

        counts = {}
        for title, _ in rows:
            counts[title] = counts.get(title, 0) + 1
        self.filter_box.blockSignals(True)
        self.filter_box.clear()
        self.filter_box.addItem(f"{ALL} ({len(rows)})", None)
        for title, n in counts.items():
            self.filter_box.addItem(f"{title} ({n})", title)
        self.filter_box.blockSignals(False)
        self.filter_box.setEnabled(bool(rows))
        if report is None:
            self.summary.setText("check_drc has not run")
            self.summary.setToolTip("")
        else:
            what = report.head[0].partition(": ")[2] if report.head else ""
            self.summary.setText((f"{len(rows)} violation(s)" if rows else "No violations")
                                 + (f", {what}" if what else ""))
            self.summary.setToolTip("\n".join(report.head + report.summary))

    def violation(self, row):
        """The Violation of a row of the table as it is sorted now."""
        return self.report.rows[self.table.item(row, NUMBER).data(Qt.UserRole)][1]

    def _filter(self):
        title = self.filter_box.currentData()
        for row in range(self.table.rowCount()):
            k = self.table.item(row, NUMBER).data(Qt.UserRole)
            self.table.setRowHidden(row, title is not None and self.report.rows[k][0] != title)

    def _moved(self, row, _col, before, _before_col):
        # With a mouse button down it is a click: cellClicked shows it.
        if row >= 0 and row != before and QApplication.mouseButtons() == Qt.NoButton:
            self._show(row)

    def _show(self, row):
        if self.report is not None and 0 <= row < self.table.rowCount():
            self.win.show_violation(self.violation(row))
