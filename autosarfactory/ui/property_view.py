import tkinter as tk
from tkinter import ttk, messagebox
from enum import Enum
import inspect
import typing
from autosarfactory import autosarfactory
from .dialogs import MultiReferenceDialog

__PAD_X__ = 5  # For some additional padding in the column width


class PropertyView:
    """
    The property view and inline editing functionality for modifying the values.
    """

    def _get_padded_text_width(self, text):
        return self._font__.measure(text + '__') + (2 * __PAD_X__)

    @staticmethod
    def _is_proxy(value) -> bool:
        """True if the value is a proxy node, i.e. a reference which could not be resolved to a model element."""
        return isinstance(value, autosarfactory.AutosarNode) and value.is_proxy()

    def _update_properties_view(self, node):
        # cancel any active inline editor before rebuilding
        self._cancel_editor()

        # references which cannot be resolved (proxy nodes) are shown in red
        self._property_view.tag_configure('proxy', foreground='red')

        # clear old properties tree values first
        self._property_view.delete(*self._property_view.get_children())
        self._property_view_id_to_node_dict.clear()
        self._property_view_id_to_edit_meta.clear()
        self._property_view_current_node = node

        # Add new values
        id = 1
        for name, value in node.get_property_values().items():
            propertyValue = ''
            if isinstance(value, dict):
                wrapper_iid = id
                id += self._add_dict_values_to_property_view(name, value, id)
                # register as multi-ref if all keys are Referrable (or dict is empty but setter expects refs)
                if self._is_ref_collection(name, value, node):
                    self._property_view_id_to_edit_meta[wrapper_iid] = (name, 'multi-ref', None)
            else:
                if isinstance(value, Enum):
                    propertyValue = value.literal if value is not None else ''
                else:
                    propertyValue = str(value) if value is not None else ''
                    if isinstance(value, autosarfactory.Referrable):
                        self._property_view_id_to_node_dict[id] = value

                # adjust column's width if necessary to fit each value
                col_w = self._get_padded_text_width(propertyValue)
                if self._property_view.column('#1', width=None) < col_w:
                    self._property_view.column('#1', width=col_w)

                self._property_view.insert('',
                                        "end",
                                        iid=id,
                                        text=name,
                                        values=(propertyValue),
                                        tags=('proxy',) if self._is_proxy(value) else ())

                # register editable rows: str/int/float/Enum/Referrable; skip File
                if name != 'File':
                    if isinstance(value, Enum):
                        self._property_view_id_to_edit_meta[id] = (name, type(value), type(value))
                    elif isinstance(value, autosarfactory.Referrable) or self._is_proxy(value):
                        self._property_view_id_to_edit_meta[id] = (name, 'ref', None)
                    elif value is None and self._setter_expects_ref(name, node):
                        self._property_view_id_to_edit_meta[id] = (name, 'ref', None)
                    elif isinstance(value, (str, int, float)) or value is None:
                        self._property_view_id_to_edit_meta[id] = (name, str if value is None else type(value), None)

                id += 1

        if isinstance(node, autosarfactory.EcucNumericalParamValue) and node.get_value() != None:
            value = node.get_value().get()
            col_w = self._get_padded_text_width(value)
            if self._property_view.column('#1', width=None) < col_w:
                self._property_view.column('#1', width=col_w)

            self._property_view.insert('',
                                        "end",
                                        iid=id,
                                        text='Value',
                                        values=(value))
            id += 1

    def _add_dict_values_to_property_view(self, name: str, value: dict, currentIdValue: int):
        wrapper_element = self._property_view.insert('',
                                    "end",
                                    iid=currentIdValue,
                                    text=name,
                                    values=(''))
        self._property_view.item(wrapper_element, open=True)
        currentIdValue += 1

        for v in value.keys():
            propertyValue = ''
            if isinstance(v, Enum):
                propertyValue = v.literal if v is not None else ''
            else:
                propertyValue = str(v) if v is not None else ''
                if isinstance(v, autosarfactory.Referrable):
                    self._property_view_id_to_node_dict[currentIdValue] = v

            # adjust column's width if necessary to fit each value
            col_w = self._get_padded_text_width(propertyValue)
            if self._property_view.column('#1', width=None) < col_w:
                self._property_view.column('#1', width=col_w)
            self._property_view.insert(wrapper_element,
                                    "end",
                                    iid=currentIdValue,
                                    text='',
                                    values=(propertyValue),
                                    tags=('proxy',) if self._is_proxy(v) else ())
            currentIdValue += 1

        return currentIdValue

    def _update_referred_by_view(self, node):
        # clear old tree values first
        self._referred_by_view.delete(*self._referred_by_view.get_children())
        self._referred_by_view_id_to_node_dict.clear()

        self._referenced_by_label.configure(text="Referenced By({} hits)".format(str(len(node.referenced_by))))
        self._referenced_by_label.update()

        id = 1
        for ref in node.referenced_by:
            text = str(ref)
            self._referred_by_view.insert('',
                                    "end",
                                    iid=id,
                                    text=text)

            # adjust column's width if necessary to fit each value
            col_w = self._get_padded_text_width(text)
            if self._referred_by_view.column('#0', width=None) < col_w:
                self._referred_by_view.column('#0', width=col_w)

            # Add to dict for later usage
            self._referred_by_view_id_to_node_dict[id] = ref
            id += 1

    def _on_referred_by_view_right_click(self, event):
        # find entry
        item = self._referred_by_view.identify('item', event.x, event.y)
        if item != '':
            self._go_to_node_id_in_asr_explorer = self._asr_explorer_node_to_id_dict[self._referred_by_view_id_to_node_dict[int(item)]]
            self._go_to_menu.tk_popup(event.x_root, event.y_root, 0)

    def _on__properties_view_right_click(self, event):
        # find entry
        item = self._property_view.identify('item', event.x, event.y)
        if item != '' and int(item) in self._property_view_id_to_node_dict:
            self._go_to_node_id_in_asr_explorer = self._asr_explorer_node_to_id_dict[self._property_view_id_to_node_dict[int(item)]]
            self._go_to_menu.tk_popup(event.x_root, event.y_root, 0)

    def _on_property_view_double_click(self, event):
        item_str = self._property_view.identify('item', event.x, event.y)
        column = self._property_view.identify_column(event.x)
        if item_str == '' or column != '#1':
            return
        iid = int(item_str)
        if iid not in self._property_view_id_to_edit_meta:
            return
        prop_name, value_type, _ = self._property_view_id_to_edit_meta[iid]
        if value_type == 'ref':
            self._start_ref_editor(iid, prop_name)
        elif value_type == 'multi-ref':
            self._open_multi_reference_editor(iid, prop_name)
        else:
            self._cancel_editor()
            self._start_editor(iid)

    def _is_ref_collection(self, name: str, value: dict, node) -> bool:
        """Return True if this dict property is a collection of Referrable nodes."""
        if value:
            return all(isinstance(k, autosarfactory.Referrable) or self._is_proxy(k) for k in value)
        # Empty dict — check setter annotation
        setter = getattr(node, self._resolve_setter_name(name), None)
        if setter is None:
            return False
        try:
            hints = typing.get_type_hints(setter)
            param_types = [v for k, v in hints.items() if k != 'return']
            if not param_types:
                return False
            args = typing.get_args(param_types[0])
            if args:
                return isinstance(args[0], type) and issubclass(args[0], autosarfactory.Referrable)
        except Exception:
            pass
        return False

    def _setter_expects_ref(self, prop_name: str, node) -> bool:
        """Return True if the setter for prop_name expects a Referrable (handles Optional[X] too)."""
        setter = getattr(node, self._resolve_setter_name(prop_name), None)
        if setter is None or not callable(setter):
            return False
        try:
            hints = typing.get_type_hints(setter)
            param_types = [v for k, v in hints.items() if k != 'return']
            if not param_types:
                return False
            ann = param_types[0]
            # Unwrap Optional[X] -> X (Optional[X] is Union[X, None])
            args = typing.get_args(ann)
            target = args[0] if args else ann
            return isinstance(target, type) and issubclass(target, autosarfactory.Referrable)
        except Exception:
            return False

    def _get_ref_element_type(self, setter):
        """
        Extract the expected element type from a setter's annotation (handles both X and list[X]).
        """
        try:
            hints = typing.get_type_hints(setter)
            param_types = [v for k, v in hints.items() if k != 'return']
            if not param_types:
                return autosarfactory.Referrable
            ann = param_types[0]
            args = typing.get_args(ann)
            return args[0] if args else ann  # list[X] -> X, X -> X
        except Exception:
            return autosarfactory.Referrable

    def _find_add_remove_methods(self, node, element_type):
        """
        Find the add_* and remove_* methods on node whose parameter matches element_type.
        """
        add_method = remove_method = None
        for method_name in dir(node):
            if not (method_name.startswith('add_') or method_name.startswith('remove_')):
                continue
            method = getattr(node, method_name, None)
            if method is None or not callable(method):
                continue
            try:
                hints = typing.get_type_hints(method)
                param_types = [v for k, v in hints.items() if k != 'return']
                if not param_types:
                    continue
                ann = param_types[0]
                if isinstance(ann, type) and issubclass(element_type, ann):
                    if method_name.startswith('add_'):
                        add_method = method
                    else:
                        remove_method = method
            except Exception:
                continue
        return add_method, remove_method

    def _open_multi_reference_editor(self, iid: int, prop_name: str):
        node = self._property_view_current_node
        if node is None:
            return
        setter_name = self._resolve_setter_name(prop_name)
        setter = getattr(node, setter_name, None)
        if setter is None or not callable(setter):
            return

        element_type = self._get_ref_element_type(setter)
        add_method, remove_method = self._find_add_remove_methods(node, element_type)
        if add_method is None or remove_method is None:
            messagebox.showwarning("Not Supported", f"Could not find add/remove methods for '{prop_name}'.", parent=self._root)
            return

        root = autosarfactory.get_root()
        candidates = autosarfactory.get_all_instances(root, element_type)

        # Current refs, in the order of the model, taken from the node itself: besides the real elements, this
        # includes the proxy nodes (unresolved references), which are not part of the property view's node dict.
        current_refs = list(getattr(node, 'get_' + setter_name[len('set_'):])())

        dialog = MultiReferenceDialog(self._root, current_refs, candidates)
        if dialog.result is None:
            return

        to_add, to_remove = dialog.result
        errors = []
        for ref in to_remove:
            try:
                remove_method(ref)
            except Exception as e:
                errors.append(f"Remove {ref.autosar_path}: {e}")
        for ref in to_add:
            try:
                add_method(ref)
            except Exception as e:
                errors.append(f"Add {ref.autosar_path}: {e}")

        if errors:
            messagebox.showerror("Errors", "\n".join(errors), parent=self._root)

        # Refresh the property view for this node to reflect changes
        self._update_properties_view(node)
        self._set_unsaved_changes(True)

    def _start_ref_editor(self, iid: int, prop_name: str):
        self._cancel_editor()
        bbox = self._property_view.bbox(iid, column='#1')
        if not bbox:
            self._property_view.see(iid)
            self._root.update_idletasks()
            bbox = self._property_view.bbox(iid, column='#1')
        if not bbox:
            return

        setter_name = self._resolve_setter_name(prop_name)
        setter = getattr(self._property_view_current_node, setter_name, None)
        if setter is None:
            return
        element_type = self._get_ref_element_type(setter)
        root = autosarfactory.get_root()
        candidates = autosarfactory.get_all_instances(root, element_type)
        if not candidates:
            messagebox.showinfo("No Candidates", "No nodes of the expected type found.", parent=self._root)
            return

        self._editing_iid = iid
        self._ref_candidates = candidates
        self._ref_filtered = [None] + list(candidates)  # None = unset

        x, y, width, height = bbox

        # Entry placed over the cell
        entry = ttk.Entry(self._property_view)
        current = self._property_view.set(iid, '#1')
        entry.insert(0, current)
        entry.select_range(0, tk.END)
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        self._active_editor = entry

        # Undecorated popup Toplevel just below the entry
        px = self._property_view.winfo_rootx() + x
        py = self._property_view.winfo_rooty() + y + height
        popup = tk.Toplevel(self._root)
        popup.wm_overrideredirect(True)
        popup_height = min(150, (len(candidates) + 1) * 18 + 4)
        popup.geometry(f'{width}x{popup_height}+{px}+{py}')
        self._ref_popup = popup

        lb_frame = tk.Frame(popup)
        lb_frame.pack(fill='both', expand=True)
        lb = tk.Listbox(lb_frame, background='white')
        vsb = ttk.Scrollbar(lb_frame, orient='vertical', command=lb.yview)
        lb.configure(yscrollcommand=vsb.set)
        lb.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        self._ref_listbox = lb
        lb.insert(tk.END, '')  # blank row = unset
        for node in candidates:
            lb.insert(tk.END, node.autosar_path)

        # Entry bindings
        entry.bind('<KeyRelease>', lambda e: self._on_ref_entry_key())
        entry.bind('<Return>', lambda e: self._commit_ref_editor())
        entry.bind('<Escape>', lambda e: self._cancel_editor())
        entry.bind('<Down>', lambda e: (lb.focus_set(), lb.selection_set(0)) if lb.size() > 0 else None)
        entry.bind('<FocusOut>', self._on_ref_entry_focus_out)

        # Listbox bindings
        lb.bind('<Return>', lambda e: self._commit_ref_editor())
        lb.bind('<Double-1>', lambda e: self._commit_ref_editor())
        lb.bind('<Escape>', lambda e: self._cancel_editor())
        lb.bind('<FocusOut>', lambda e: self._cancel_editor())

    def _on_ref_entry_key(self):
        if self._active_editor is None:
            return
        text = self._active_editor.get().lower()
        matched = [n for n in self._ref_candidates
                   if not text or text in n.autosar_path.lower()]
        self._ref_filtered = [None] + matched  # None always first = unset
        lb = self._ref_listbox
        lb.delete(0, tk.END)
        lb.insert(tk.END, '')  # blank row = unset
        for node in matched:
            lb.insert(tk.END, node.autosar_path)

    def _on_ref_entry_focus_out(self, event):
        # Don't cancel if focus moved to the popup listbox
        if self._root.focus_get() is self._ref_listbox:
            return
        self._cancel_editor()

    def _commit_ref_editor(self):
        if self._editing_iid is None or self._property_view_current_node is None:
            self._cancel_editor()
            return

        iid = self._editing_iid
        lb = self._ref_listbox
        sel = lb.curselection()
        if sel:
            selected_node = self._ref_filtered[sel[0]]  # may be None (blank row)
        else:
            # match entry text exactly against autosar_path; empty text -> unset
            text = self._active_editor.get() if self._active_editor else ''
            if text == '':
                selected_node = None
            else:
                matched = [n for n in self._ref_filtered
                           if n is not None and n.autosar_path == text]
                if not matched:
                    self._cancel_editor()
                    return
                selected_node = matched[0]

        prop_name = self._property_view_id_to_edit_meta[iid][0]
        setter_name = self._resolve_setter_name(prop_name)
        setter = getattr(self._property_view_current_node, setter_name, None)

        # Clear state before calling setter (guards re-entrant FocusOut)
        self._editing_iid = None
        self._active_editor.destroy()
        self._active_editor = None
        self._ref_popup.destroy()
        self._ref_popup = None
        self._ref_listbox = None

        if setter is None:
            return
        try:
            setter(selected_node)
        except Exception as e:
            messagebox.showerror("Cannot Set Reference", str(e), parent=self._root)
            return

        display = str(selected_node) if selected_node is not None else ''
        self._property_view.set(iid, '#1', display)
        # the reference is now a real element (or empty), so it is no longer shown as unresolved
        self._property_view.item(iid, tags=())
        self._set_unsaved_changes(True)

    def _start_editor(self, iid: int):
        bbox = self._property_view.bbox(iid, column='#1')
        if not bbox:
            self._property_view.see(iid)
            self._root.update_idletasks()
            bbox = self._property_view.bbox(iid, column='#1')
        if not bbox:
            return

        x, y, width, height = bbox
        prop_name, value_type, enum_class = self._property_view_id_to_edit_meta[iid]
        current_display = self._property_view.set(iid, '#1')
        self._editing_iid = iid

        if enum_class is not None:
            literals = [member.literal for member in enum_class]
            editor = ttk.Combobox(self._property_view, values=literals, state='readonly')
            if current_display in literals:
                editor.set(current_display)
            editor.bind('<<ComboboxSelected>>', lambda e: self._commit_editor())
            editor.bind('<Escape>', lambda e: self._cancel_editor())
        else:
            editor = ttk.Entry(self._property_view)
            editor.insert(0, current_display)
            editor.select_range(0, tk.END)
            editor.bind('<Return>', lambda e: self._commit_editor())
            editor.bind('<Escape>', lambda e: self._cancel_editor())

        editor.bind('<FocusOut>', lambda e: self._commit_editor())
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        self._active_editor = editor

    def _commit_editor(self):
        if self._active_editor is None or self._editing_iid is None:
            return

        iid = self._editing_iid
        editor = self._active_editor
        # Clear references first to guard against re-entrant FocusOut calls
        self._active_editor = None
        self._editing_iid = None

        meta = self._property_view_id_to_edit_meta.get(iid)
        if meta is None or self._property_view_current_node is None:
            editor.destroy()
            return

        prop_name, value_type, enum_class = meta
        raw_text = editor.get()
        editor.destroy()

        try:
            if enum_class is not None:
                new_value = next((m for m in enum_class if m.literal == raw_text), None)
                if new_value is None:
                    return
                display_value = new_value.literal
            elif value_type == int:
                new_value = int(raw_text)
                display_value = str(new_value)
            elif value_type == float:
                new_value = float(raw_text)
                display_value = str(new_value)
            else:
                new_value = raw_text if raw_text != '' else None
                display_value = raw_text
        except (ValueError, TypeError):
            return

        setter_name = self._resolve_setter_name(prop_name)
        if setter_name is None:
            return
        node = self._property_view_current_node
        setter = getattr(node, setter_name, None)
        if setter is None or not callable(setter):
            return

        # For ShortName: look up the tree ID *before* the setter changes node.path
        # (AutosarNode.__hash__ is based on path, so the hash changes after rename)
        tree_id = None
        if prop_name == 'ShortName':
            tree_id = self._asr_explorer_node_to_id_dict.get(node)

        try:
            setter(new_value)
        except Exception:
            return

        self._property_view.set(iid, '#1', display_value)
        self._set_unsaved_changes(True)

        if prop_name == 'ShortName' and tree_id is not None:
            # Node hash has changed — update the dict entry under the new hash
            self._asr_explorer_node_to_id_dict[node] = tree_id
            self._asr_explorer.item(str(tree_id), text=node.name or node.__class__.__name__)

    def _cancel_editor(self):
        if self._active_editor is not None:
            self._active_editor.destroy()
            self._active_editor = None
        if self._ref_popup is not None:
            self._ref_popup.destroy()
            self._ref_popup = None
        self._ref_listbox = None
        self._editing_iid = None

    def _resolve_setter_name(self, prop_name: str):
        if not prop_name:
            return None
        return 'set_' + prop_name[0].lower() + prop_name[1:]

    def _set_unsaved_changes(self, has_changes: bool):
        self._has_unsaved_changes = has_changes
        self._root.title(('* ' if has_changes else '') + 'Autosar Viewer')

    def _save(self):
        if not self._has_unsaved_changes:
            return
        try:
            autosarfactory.save()
            self._set_unsaved_changes(False)
        except Exception as e:
            messagebox.showerror("Save Failed", str(e))
