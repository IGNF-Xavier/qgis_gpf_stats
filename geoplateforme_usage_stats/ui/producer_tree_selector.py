"""Tree-structured selector for the Producteur tab (feedback: a flat list of
~300 offerings/endpoints/permissions/groups was hard to browse and gave no
visibility into what a group actually contains).

Structure: category (Groupes utilisateur / Endpoints / Offerings /
Permissions producteur) → datastore (for the high-cardinality categories) →
leaf. A group's own leaf can be expanded to preview its member offerings
(read-only - membership is still edited in the group composer).

Selection state lives in a single ``{item_id: entry}`` dict rather than by
physically moving tree nodes: leaves are marked (prefix + bold) instead of
removed, which keeps the tree structure stable and re-filterable at all
times.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

CATEGORY_ORDER = ("user_group", "endpoint", "offering", "producer_permission")
CATEGORY_LABELS = {
    "user_group": "👥 Groupes utilisateur",
    "endpoint": "🔌 Endpoints",
    "offering": "🧩 Offerings",
    "producer_permission": "🔑 Permissions producteur",
}
DATASTORE_GROUPED_CATEGORIES = {"endpoint", "offering", "producer_permission"}
SELECTED_PREFIX = "✓ "


def _tooltip_for(entry) -> str:
    parts = [f"UUID : {entry.item_id}"]
    if getattr(entry, "datastore_name", ""):
        parts.append(f"Datastore : {entry.datastore_name}")
    if getattr(entry, "service_type", ""):
        parts.append(f"Type : {entry.service_type}")
    if getattr(entry, "stats_path", ""):
        parts.append(f"Route : {entry.stats_path}")
    return "\n".join(parts)


class ProducerTreeSelector(QWidget):
    selectionChanged = pyqtSignal()

    def __init__(self, available_title: str, selected_title: str, parent=None):
        super().__init__(parent)
        self._entries_by_category: dict[str, list] = {}
        self._groups_by_id: dict = {}
        self._offerings_by_id: dict = {}
        self._selected_by_id: dict = {}
        self._leaf_items: dict[str, QTreeWidgetItem] = {}

        root = QVBoxLayout(self)
        body = QHBoxLayout()
        root.addLayout(body)

        available_box = QVBoxLayout()
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{available_title}</b>"))
        header.addStretch()
        self.available_count = QLabel()
        header.addWidget(self.available_count)
        available_box.addLayout(header)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher (nom, datastore, type)…")
        self.search.textChanged.connect(self._apply_filter)
        available_box.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Shift / Ctrl
        self.tree.itemDoubleClicked.connect(self._on_tree_double_clicked)
        available_box.addWidget(self.tree, 1)
        body.addLayout(available_box, 2)

        buttons = QVBoxLayout()
        buttons.addStretch()
        self.btn_add_all = QPushButton(">>")
        self.btn_add_selected = QPushButton(">>>")
        self.btn_remove_selected = QPushButton("<<<")
        self.btn_remove_all = QPushButton("<<")
        for button, slot, tip in (
            (self.btn_add_selected, self._add_selected, "Ajouter la sélection (Maj/Ctrl pour plusieurs ; une catégorie ou un datastore ajoute tout son contenu visible)"),
            (self.btn_remove_selected, self._remove_selected, "Retirer les éléments sélectionnés"),
            (self.btn_add_all, self._add_all, "Tout ajouter"),
            (self.btn_remove_all, self._remove_all, "Tout retirer"),
        ):
            button.setMinimumWidth(70)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        body.addLayout(buttons)

        selected_box = QVBoxLayout()
        header2 = QHBoxLayout()
        header2.addWidget(QLabel(f"<b>{selected_title}</b>"))
        header2.addStretch()
        self.selected_count = QLabel()
        header2.addWidget(self.selected_count)
        selected_box.addLayout(header2)
        self.selected_search = QLineEdit()
        self.selected_search.setPlaceholderText("Rechercher…")
        self.selected_search.textChanged.connect(self._apply_selected_filter)
        selected_box.addWidget(self.selected_search)
        self.selected_list = QListWidget()
        self.selected_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.selected_list.itemDoubleClicked.connect(self._on_selected_double_clicked)
        selected_box.addWidget(self.selected_list, 1)
        body.addLayout(selected_box, 2)

    # -- building the tree ------------------------------------------------
    def set_available(self, entries, groups_by_id: dict | None = None) -> None:
        self._groups_by_id = groups_by_id or {}
        self._selected_by_id = {}
        self._leaf_items = {}
        by_category: dict[str, list] = {}
        for entry in entries:
            by_category.setdefault(getattr(entry, "kind", ""), []).append(entry)
        self._entries_by_category = by_category
        self._offerings_by_id = {e.offering_id: e for e in by_category.get("offering", [])}

        self.tree.clear()
        for category in CATEGORY_ORDER:
            items = by_category.get(category, [])
            if not items:
                continue
            category_node = QTreeWidgetItem([f"{CATEGORY_LABELS[category]} ({len(items)})"])
            category_node.setFont(0, self._bold_font())
            category_node.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(category_node)

            if category == "user_group":
                for group_entry in sorted(items, key=lambda e: e.label.casefold()):
                    self._add_group_node(category_node, group_entry)
            elif category in DATASTORE_GROUPED_CATEGORIES:
                by_datastore: dict[str, list] = {}
                for entry in items:
                    by_datastore.setdefault(getattr(entry, "datastore_name", "") or "(sans datastore)", []).append(entry)
                for datastore_name in sorted(by_datastore):
                    datastore_items = by_datastore[datastore_name]
                    datastore_node = QTreeWidgetItem([f"{datastore_name} ({len(datastore_items)})"])
                    datastore_node.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    category_node.addChild(datastore_node)
                    for entry in sorted(datastore_items, key=lambda e: e.label.casefold()):
                        self._add_leaf(datastore_node, entry)
            else:
                for entry in sorted(items, key=lambda e: e.label.casefold()):
                    self._add_leaf(category_node, entry)

        self.tree.expandToDepth(0)
        self.selected_list.clear()
        self._refresh_counts()

    def _bold_font(self) -> QFont:
        font = QFont(self.font())
        font.setBold(True)
        return font

    def _add_leaf(self, parent: QTreeWidgetItem, entry) -> QTreeWidgetItem:
        item = QTreeWidgetItem([entry.label])
        item.setData(0, Qt.UserRole, entry)
        item.setToolTip(0, _tooltip_for(entry))
        parent.addChild(item)
        self._leaf_items[entry.item_id] = item
        return item

    def _add_group_node(self, parent: QTreeWidgetItem, group_entry) -> None:
        item = self._add_leaf(parent, group_entry)
        group = self._groups_by_id.get(group_entry.group_id)
        if not group or not group.offering_ids:
            empty = QTreeWidgetItem(["(groupe vide)"])
            empty.setFlags(Qt.NoItemFlags)
            empty.setForeground(0, QColor("#999999"))
            item.addChild(empty)
            return
        for offering_id in group.offering_ids:
            offering = self._offerings_by_id.get(offering_id)
            label = offering.label if offering else f"offering {offering_id} (hors catalogue chargé)"
            preview = QTreeWidgetItem([f"· {label}"])
            preview.setFlags(Qt.NoItemFlags)
            preview.setForeground(0, QColor("#888888"))
            item.addChild(preview)

    # -- selection state ---------------------------------------------------
    def _leaf_style(self, item: QTreeWidgetItem, entry) -> None:
        selected = entry.item_id in self._selected_by_id
        item.setText(0, (SELECTED_PREFIX if selected else "") + entry.label)
        font = item.font(0)
        font.setBold(selected)
        item.setFont(0, font)
        item.setForeground(0, QColor("#1F4E78") if selected else QColor("#000000"))

    def _refresh_counts(self) -> None:
        total_leaves = len(self._leaf_items)
        self.available_count.setText(f"{total_leaves} élément(s)")
        self.selected_count.setText(f"{len(self._selected_by_id)} élément(s)")

    def _rebuild_selected_list(self) -> None:
        self.selected_list.clear()
        for entry in sorted(self._selected_by_id.values(), key=lambda e: e.label.casefold()):
            item = QListWidgetItem(entry.label)
            item.setData(Qt.UserRole, entry)
            item.setToolTip(_tooltip_for(entry))
            self.selected_list.addItem(item)
        self._apply_selected_filter(self.selected_search.text())
        self._refresh_counts()

    def _set_selected(self, entries, selected: bool) -> None:
        changed = False
        for entry in entries:
            already = entry.item_id in self._selected_by_id
            if selected and not already:
                self._selected_by_id[entry.item_id] = entry
                changed = True
            elif not selected and already:
                del self._selected_by_id[entry.item_id]
                changed = True
            leaf = self._leaf_items.get(entry.item_id)
            if leaf is not None:
                self._leaf_style(leaf, entry)
        if changed:
            self._rebuild_selected_list()
            self.selectionChanged.emit()

    # -- tree interaction ---------------------------------------------------
    def _on_tree_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        entry = item.data(0, Qt.UserRole)
        if entry is None:
            return
        self._set_selected([entry], entry.item_id not in self._selected_by_id)

    def _on_selected_double_clicked(self, item: QListWidgetItem) -> None:
        entry = item.data(Qt.UserRole)
        if entry is not None:
            self._set_selected([entry], False)

    def _descendant_leaves(self, item: QTreeWidgetItem) -> list:
        """The item itself if it is a selectable object, otherwise every visible
        object below it (a category or datastore header stands for its content)."""
        if item.data(0, Qt.UserRole) is not None:
            return [item]
        leaves = []
        for i in range(item.childCount()):
            child = item.child(i)
            if child.isHidden() or child.flags() == Qt.NoItemFlags:
                continue
            leaves.extend(self._descendant_leaves(child))
        return leaves

    def _tree_leaf_entries(self, only_selected_nodes: bool) -> list:
        if only_selected_nodes:
            leaf_items = [leaf for node in self.tree.selectedItems() for leaf in self._descendant_leaves(node)]
        else:
            leaf_items = list(self._leaf_items.values())
        entries = {}
        for leaf in leaf_items:
            entry = leaf.data(0, Qt.UserRole)
            if entry is not None and not leaf.isHidden():
                entries[entry.item_id] = entry
        return list(entries.values())

    def _add_selected(self) -> None:
        self._set_selected(self._tree_leaf_entries(only_selected_nodes=True), True)

    def _remove_selected(self) -> None:
        entries = [
            self.selected_list.item(i).data(Qt.UserRole)
            for i in range(self.selected_list.count())
            if self.selected_list.item(i).isSelected()
        ]
        self._set_selected(entries, False)

    def _add_all(self) -> None:
        self._set_selected(self._tree_leaf_entries(only_selected_nodes=False), True)

    def _remove_all(self) -> None:
        self._set_selected(list(self._selected_by_id.values()), False)

    # -- filtering ----------------------------------------------------------
    def _apply_filter(self, text: str) -> None:
        needle = text.casefold().strip()
        for i in range(self.tree.topLevelItemCount()):
            self._filter_node(self.tree.topLevelItem(i), needle)

    def _filter_node(self, node: QTreeWidgetItem, needle: str) -> bool:
        if node.data(0, Qt.UserRole) is not None:
            visible = not needle or needle in node.text(0).casefold()
            node.setHidden(not visible)
            return visible
        any_visible = False
        for i in range(node.childCount()):
            child = node.child(i)
            if child.flags() == Qt.NoItemFlags:
                continue  # group-member preview row, not filterable/selectable on its own
            if self._filter_node(child, needle):
                any_visible = True
        node.setHidden(not any_visible)
        return any_visible

    def _apply_selected_filter(self, text: str) -> None:
        needle = text.casefold().strip()
        for i in range(self.selected_list.count()):
            item = self.selected_list.item(i)
            item.setHidden(bool(needle and needle not in item.text().casefold()))

    # -- public API matching DualSelector ------------------------------------
    def selected_items(self) -> list:
        return list(self._selected_by_id.values())
