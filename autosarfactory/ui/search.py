import tkinter as tk
from tkinter import ttk
import re
from autosarfactory import autosarfactory

__PAD_X__ = 5  # For some additional padding in the column width


class Search:
    """Mixin providing the search view functionality."""

    def _on_search_entry_click(self, event):
        search_string = self._search_field.get()
        search_nodes = []
        search_type = self._search_dropdown.get()
        if search_string == 'search':
            self._search_field.delete(0, "end") # delete all the text in the entry
            self._search_field.insert(0, '') #Insert blank for user input
            self._search_field.config(foreground='black')
        elif search_string != '':
            if search_type == "Short Name":
                for node in self._asr_explorer_id_to_node_dict.values():
                    if node.name is not None and search_string.lower() in node.name.lower():
                        search_nodes.append(node)
            elif search_type == "Autosar Type":
                for node in self._asr_explorer_id_to_node_dict.values():
                    node_type = node.__class__.__name__
                    if node_type is not None and search_string.lower() in node_type.lower():
                        search_nodes.append(node)
            elif search_type == "Regular Expression":
                for node in self._asr_explorer_id_to_node_dict.values():
                    if node.name is not None:
                        if search_string=='*' or search_string=='+':
                            search_string="\{0}".format(search_string)
                        matched_re = re.search(search_string, node.name)
                        if matched_re is not None and matched_re.group()!='':
                            search_nodes.append(node)
        self._update_search_view(search_nodes)

    def _on_search_entry_focusout(self, event):
        if self._search_field.get() == '':
            self._search_field.insert(0, 'search')
            self._search_field.config(foreground='grey')

    def _update_search_view(self, nodes):
        # clear old search tree values first
        self._search_view.delete(*self._search_view.get_children())
        self._search_view_id_to_node_dict.clear()

        self._search_results_label.configure(text="Results({} hits)".format(str(len(nodes))))
        self._search_results_label.update()
        # Add new values
        id = 1
        for node in nodes:
            text = str(node)
            self._search_view.insert('',
                                        "end",
                                        iid=id,
                                        text=text)

            # adjust column's width if necessary to fit each value
            col_w = self._get_padded_text_width(text)
            if self._search_view.column('#0', width=None) < col_w:
                self._search_view.column('#0', width=col_w)

            # Add to dict for later usage
            self._search_view_id_to_node_dict[id] = node
            id += 1

    def _search_view_select_node(self, item):
        if item != '':
            self._go_to_node_id_in_asr_explorer = self._asr_explorer_node_to_id_dict[self._search_view_id_to_node_dict[int(item)]]
            self._go_to_node_in_asr_explorer()

    def _on_search_view_selection(self, event):
        self._search_view_select_node(self._search_view.identify('item', event.x, event.y))

    def _on_search_view_key_released(self, event):
        self._search_view_select_node(self._search_view.focus())
