import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import itertools
import typing
from autosarfactory import autosarfactory
from . import graph_gen


class ARExplorer:
    
    def _init_tree(self):
        # clear all items in tree if it exists
        self._asr_explorer_id_to_node_dict.clear()
        self._asr_explorer_node_to_id_dict.clear()
        self._referred_by_view_id_to_node_dict.clear()
        self._property_view_id_to_node_dict.clear()
        self._search_view_id_to_node_dict.clear()
        if self._asr_explorer.get_children():
            self._asr_explorer.delete(*self._asr_explorer.get_children())
            self._asr_explorer.update()

    def _populate_tree(self, autosar_root):
        self._init_tree()
        self._set_unsaved_changes(False)
        idCounter = itertools.count()
        id = next(idCounter)
        root_tree = self._asr_explorer.insert('', 'end', iid=id, text="AutosarRoot", values=('AUTOSAR'))
        self._asr_explorer_id_to_node_dict[id] = autosar_root
        self._asr_explorer_node_to_id_dict[autosar_root] = id
        self._add_child(autosar_root, root_tree, idCounter)

    def _add_child(self, node, parentItem, idCounter):
        if hasattr(node, 'get_children') and callable(getattr(node, 'get_children')):
            for child in node.get_children():
                childTree = self._create_tree_item(child, parentItem, idCounter)
                if isinstance(child, autosarfactory.EcucParameterValue):
                    continue

                # add child nodes
                self._add_child(child, childTree, idCounter)

    def _create_tree_item(self, node, parentItem, idCounter):
        id = next(idCounter)
        self._asr_explorer_id_to_node_dict[id] = node
        self._asr_explorer_node_to_id_dict[node] = id

        if node.name is not None:
            element_text = node.name
        elif isinstance(node, autosarfactory.EcucParameterValue) or isinstance(node, autosarfactory.EcucAbstractReferenceValue):
            defRef = node._node.find('{*}DEFINITION-REF')
            if defRef is not None and defRef.text != '' and '/' in defRef.text:
                element_text = defRef.text.split("/")[-1]
            else:
                element_text = node.__class__.__name__
        else:
            element_text = node.__class__.__name__

        type_text = str(node)
        """
        # adjust column's width if necessary to fit each value
        col_w = self._get_padded_text_width(element_text)
        if self._asr_explorer.column('#0',width=None) < col_w:
            self._asr_explorer.column('#0', width=col_w)

        col_w = self._get_padded_text_width(type_text)
        if self._asr_explorer.column('#1',width=None) < col_w:
            self._asr_explorer.column('#1', width=col_w)
        """

        return self._asr_explorer.insert(parentItem,
                                    "end",
                                    iid=id,
                                    text=element_text,
                                    values=type_text.replace('"', '\\"'))

    def _open_node(self, id):
        parent_id = self._asr_explorer.parent(id)
        if parent_id != '':
            self._open_node(parent_id)
        self._asr_explorer.item(id, open=True)

    def _go_to_node_in_asr_explorer(self):
        if self._go_to_node_id_in_asr_explorer is not None:
            self._open_node(self._asr_explorer.parent(self._go_to_node_id_in_asr_explorer))
            self._asr_explorer.selection_set(self._go_to_node_id_in_asr_explorer)
            self._asr_explorer.focus(self._go_to_node_id_in_asr_explorer)
            self._asr_explorer.see(self._go_to_node_id_in_asr_explorer)

            # Update the views
            node = self._asr_explorer_id_to_node_dict[int(self._go_to_node_id_in_asr_explorer)]
            self._update_properties_view(node)
            self._update_referred_by_view(node)

    def _select_node(self, item):
        if item != '':
            node = self._asr_explorer_id_to_node_dict[int(item)]
            self._update_properties_view(node)
            self._update_referred_by_view(node)

    def _on_asr_explorer_selection(self, event):
        # find entry
        self._select_node(self._asr_explorer.identify('item', event.x, event.y))

    def _on_asr_explorer_key_released(self, event):
        self._select_node(self._asr_explorer.focus())

    def _on__asr_explorer_right_click(self, event):
        item = self._asr_explorer.identify('item', event.x, event.y)
        self._go_to_node_id_in_asr_explorer = item
        self._right_click_event = event  # store for popup positioning
        self._asr_explorer_menu.tk_popup(event.x_root, event.y_root, 0)

    def _open_new_element_popup(self):
        item = self._go_to_node_id_in_asr_explorer
        if not item or int(item) not in self._asr_explorer_id_to_node_dict:
            return
        node = self._asr_explorer_id_to_node_dict[int(item)]

        factory_methods = {}  # label -> (method, parent_node)
        for method_name in sorted(dir(node)):
            if not method_name.startswith('new_'):
                continue
            method = getattr(node, method_name, None)
            if method is None or not callable(method):
                continue
            label = method_name[4:]
            factory_methods[label] = (method, node, item)

        if not factory_methods:
            return

        all_labels = list(factory_methods.keys())
        event = self._right_click_event

        popup = tk.Toplevel(self._root)
        popup.wm_overrideredirect(True)
        popup.geometry(f'280x220+{event.x_root}+{event.y_root}')

        frame = tk.Frame(popup, relief='solid', borderwidth=1)
        frame.pack(fill='both', expand=True)

        filter_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=filter_var)
        entry.pack(fill='x', padx=4, pady=(4, 2))

        lb_frame = tk.Frame(frame)
        lb_frame.pack(fill='both', expand=True, padx=4, pady=(0, 4))
        lb = tk.Listbox(lb_frame, background='white', activestyle='dotbox')
        vsb = ttk.Scrollbar(lb_frame, orient='vertical', command=lb.yview)
        lb.configure(yscrollcommand=vsb.set)
        lb.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        filtered = list(all_labels)

        def refresh_list(*_):
            nonlocal filtered
            text = filter_var.get().lower()
            filtered = [l for l in all_labels if not text or text in l.lower()]
            lb.delete(0, tk.END)
            for l in filtered:
                lb.insert(tk.END, l)
            if filtered:
                lb.selection_set(0)
                lb.activate(0)

        def commit():
            sel = lb.curselection()
            if not sel:
                return
            label = filtered[sel[0]]
            popup.destroy()
            m, n, iid = factory_methods[label]
            self._create_new_element(m, n, label, iid)

        filter_var.trace_add('write', refresh_list)
        entry.bind('<Return>', lambda e: commit())
        entry.bind('<Escape>', lambda e: popup.destroy())
        entry.bind('<Down>', lambda e: (lb.focus_set(), lb.selection_set(0), lb.activate(0)))
        lb.bind('<Return>', lambda e: commit())
        lb.bind('<Double-1>', lambda e: commit())
        lb.bind('<Escape>', lambda e: popup.destroy())
        lb.bind('<FocusOut>', lambda e: popup.after(50, lambda: popup.destroy()
                                                    if popup.focus_get() not in (entry, lb) else None))
        popup.bind('<FocusOut>', lambda e: popup.after(100, lambda: popup.destroy()
                                                       if not str(popup.focus_get()).startswith(str(popup)) else None))

        refresh_list()
        entry.focus_set()

    def _create_new_element(self, factory_method, parent_node, element_type_name, parent_iid):
        # Determine return type to decide whether we need a name
        try:
            hints = typing.get_type_hints(factory_method)
            return_type = hints.get('return')
        except Exception:
            return_type = None

        needs_name = (return_type is not None and
                      isinstance(return_type, type) and
                      issubclass(return_type, autosarfactory.Referrable))

        name = None
        if needs_name:
            # Count existing siblings of the same type to generate the next name
            getter_name = 'get_' + element_type_name[0].lower() + element_type_name[1:] + 's'
            getter = getattr(parent_node, getter_name, None)
            if getter and callable(getter):
                count = len(list(getter()))
            else:
                count = len([c for c in parent_node.get_children()
                             if type(c).__name__ == element_type_name])
            name = f'{element_type_name}_{count + 1}'

        try:
            new_node = factory_method(name) if needs_name else factory_method()
        except Exception as e:
            messagebox.showerror("Create Failed", str(e), parent=self._root)
            return

        idCounter = itertools.count(max(self._asr_explorer_id_to_node_dict.keys(), default=0) + 1)
        child_iid = self._create_tree_item(new_node, parent_iid, idCounter)
        self._asr_explorer.item(parent_iid, open=True)
        self._asr_explorer.selection_set(child_iid)
        self._asr_explorer.see(child_iid)
        self._update_properties_view(new_node)
        self._update_referred_by_view(new_node)
        self._set_unsaved_changes(True)

    def _delete_element(self):
        item = self._go_to_node_id_in_asr_explorer
        if not item or int(item) not in self._asr_explorer_id_to_node_dict:
            return

        node = self._asr_explorer_id_to_node_dict[int(item)]
        parent_node = node.get_parent()
        if parent_node is None:
            messagebox.showwarning("Cannot Delete", "This element has no parent and cannot be removed.", parent=self._root)
            return

        # Derive delete callable from class name using naming conventions:
        #   collection child: remove_hwPin  (remove_ + first letter lowercased)
        #   singular child:   set_swDataDefProps(None)  (set_ + first letter lowercased)
        class_name = type(node).__name__
        name_suffix = class_name[0].lower() + class_name[1:]
        remove_method = getattr(parent_node, 'remove_' + name_suffix, None)
        delete_callable = None
        delete_arg = None
        if remove_method is not None and callable(remove_method):
            delete_callable = remove_method
            delete_arg = node
        else:
            setter = getattr(parent_node, 'set_' + name_suffix, None)
            if setter is not None and callable(setter):
                delete_callable = setter
                delete_arg = None  # set to None = unset

        if delete_callable is None:
            messagebox.showwarning("Cannot Delete", f"No remove/set method found for {class_name} on its parent.", parent=self._root)
            return

        label = node.name or type(node).__name__
        if not messagebox.askyesno("Delete Element", f"Delete '{label}'? This cannot be undone.", parent=self._root):
            return

        try:
            delete_callable(delete_arg)
        except Exception as e:
            messagebox.showerror("Delete Failed", str(e), parent=self._root)
            return

        # Remove tree item and all its descendants from dicts
        self._remove_tree_item_recursive(item)
        self._set_unsaved_changes(True)

        # Clear property/referred-by views if they were showing the deleted node
        if self._property_view_current_node is node:
            self._property_view.delete(*self._property_view.get_children())
            self._property_view_id_to_node_dict.clear()
            self._property_view_id_to_edit_meta.clear()
            self._property_view_current_node = None
            self._referred_by_view.delete(*self._referred_by_view.get_children())
            self._referred_by_view_id_to_node_dict.clear()

    def _remove_tree_item_recursive(self, iid):
        """Remove a tree item and all its descendants from the tree and lookup dicts."""
        for child_iid in self._asr_explorer.get_children(iid):
            self._remove_tree_item_recursive(child_iid)
        node = self._asr_explorer_id_to_node_dict.pop(int(iid), None)
        if node is not None:
            self._asr_explorer_node_to_id_dict.pop(node, None)
        self._asr_explorer.delete(iid)

    def _generate_graph(self):
        item = self._go_to_node_id_in_asr_explorer
        if item != '' and int(item) in self._asr_explorer_id_to_node_dict:
            node = self._asr_explorer_id_to_node_dict[int(item)]
            options = { 'defaultextension': '.html',
                        'filetypes': [ ('HTML', '*.html')],
                        'title': 'Save Graph As...'}

            filepath = filedialog.asksaveasfilename(**options)
            if filepath:
                graph_gen.create_graph_report(node, output_filename=filepath)

    def _copy_name_to_clip_board(self):
        item = self._go_to_node_id_in_asr_explorer
        if item != '' and int(item) in self._asr_explorer_id_to_node_dict:
            self._root.clipboard_clear()
            self._root.clipboard_append(self._asr_explorer_id_to_node_dict[int(item)].name)

    def _copy_path_to_clip_board(self):
        item = self._go_to_node_id_in_asr_explorer
        if item != '' and int(item) in self._asr_explorer_id_to_node_dict:
            self._root.clipboard_clear()
            self._root.clipboard_append(self._asr_explorer_id_to_node_dict[int(item)].path)

    def _copy_file_path_to_clip_board(self):
        item = self._go_to_node_id_in_asr_explorer
        if item != '' and int(item) in self._asr_explorer_id_to_node_dict:
            self._root.clipboard_clear()
            self._root.clipboard_append(self._asr_explorer_id_to_node_dict[int(item)].file)

    def _refresh_asr_explorer_label(self, node):
        node_id = self._asr_explorer_node_to_id_dict.get(node)
        if node_id is not None:
            self._asr_explorer.item(str(node_id), text=node.name or node.__class__.__name__)
