import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from autosarfactory import autosarfactory


class LoadModelsDialog(tk.Toplevel):
    """
    A modal dialog for selecting files/folders
    """
    def __init__(self, parent, existing_files =[]):
        super().__init__(parent)

        self.transient(parent)
        self.title("Load Models")
        self.geometry("600x450")
        self.resizable(False, False)

        self.selected_paths = existing_files
        self.result = None
        self.autosarRoot = None
        self.worker_thread = None
        self.loading_error = None
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.grab_set()
        self.position_center()
        self.wait_window(self)

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        list_frame = ttk.LabelFrame(main_frame, text="Selected Files and Folders")
        list_frame.pack(fill="both", expand=True, pady=5)

        self.path_listbox = tk.Listbox(list_frame, background="white")
        self.path_listbox.pack(side="left", fill="both", expand=True, padx=(5,0), pady=5)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.path_listbox.yview)
        scrollbar.pack(side="right", fill="y", padx=(0,5), pady=5)
        self.path_listbox.config(yscrollcommand=scrollbar.set)
        self._update_listbox()

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=5)

        self.add_files_btn = ttk.Button(button_frame, text="Add File(s)...", command=self._add_files)
        self.add_folder_btn = ttk.Button(button_frame, text="Add Folder(s)...", command=self._add_folder)
        self.remove_btn = ttk.Button(button_frame, text="Remove Selected", command=self._remove_selected)

        self.add_files_btn.pack(side="left", padx=5)
        self.add_folder_btn.pack(side="left", padx=5)
        self.remove_btn.pack(side="left", padx=5)

        # --- Progress Bar Widgets ---
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_label = ttk.Label(self.progress_frame, text="Loading...")
        self.progress_bar = ttk.Progressbar(self.progress_frame, orient='horizontal', mode='indeterminate')
        self.progress_label.pack(fill="x")
        self.progress_bar.pack(fill="x", pady=5)

        # --- OK/Cancel Frame ---
        ok_cancel_frame = ttk.Frame(main_frame)
        ok_cancel_frame.pack(side="bottom", fill="x", pady=(10, 0))

        self.load_btn = ttk.Button(ok_cancel_frame, text="Load", command=self._on_load)
        self.cancel_btn = ttk.Button(ok_cancel_frame, text="Cancel", command=self._on_cancel)
        self.load_btn.pack(side="right", padx=5)
        self.cancel_btn.pack(side="right")

    def _toggle_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        self.load_btn.config(state=state)
        self.cancel_btn.config(state=state)
        self.add_files_btn.config(state=state)
        self.add_folder_btn.config(state=state)
        self.remove_btn.config(state=state)

    def _add_files(self):
        paths = filedialog.askopenfilenames( title="Select ARXML file(s)", parent=self, filetypes=[("ARXML files", "*.arxml")])
        if paths:
            self.selected_paths.extend(paths)
            self._update_listbox()

    def _add_folder(self):
        path = filedialog.askdirectory(title="Select a folder", parent=self)
        if path:
            self.selected_paths.append(path)
            self._update_listbox()

    def _remove_selected(self):
        selected_indices = self.path_listbox.curselection()
        for i in sorted(selected_indices, reverse=True):
            del self.selected_paths[i]
        self._update_listbox()

    def _update_listbox(self):
        self.path_listbox.delete(0, tk.END)
        for path in sorted(set(self.selected_paths)):
            self.path_listbox.insert(tk.END, path)

    def _on_load(self):
        self.result = sorted(set(self.selected_paths))
        if not self.result:
            messagebox.showwarning("No Selection", "Please add at least one file or folder.", parent=self)
            return

        self._toggle_controls(enabled=False)
        self.loading_error = None
        self.protocol("WM_DELETE_WINDOW", lambda: None) # Disable closing of the modal when loading is in progress

        # This line will now correctly place the progress bar above the Load/Cancel buttons
        self.progress_frame.pack(side="bottom", fill="x", before=self.load_btn.master, pady=(10,0))
        self.progress_bar.start()

        self.worker_thread = threading.Thread(target=self._loading_worker, args=(self.result,))
        self.worker_thread.start()
        self.after(100, self._check_thread_status)

    def position_center(self):
        self.update_idletasks()
        parent = self.master
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _loading_worker(self, paths_to_load):
        autosarfactory.reinit() #clear all the state and load the new models
        root, status = autosarfactory.read(paths_to_load)
        if status:
            self.autosarRoot = root
            self.loading_error = None
        else:
            self.autosarRoot = None
            self.loading_error = "An error occurred during loading!"

    def _check_thread_status(self):
        if self.worker_thread.is_alive():
            self.after(100, self._check_thread_status)
            return

        # The thread is finished, so stop the progress bar animation
        self.progress_bar.stop()

        if self.loading_error:
            messagebox.showerror("Loading Failed", self.loading_error, parent=self)
            self.progress_frame.pack_forget()
            self._toggle_controls(enabled=True)
            self.protocol("WM_DELETE_WINDOW", self._on_cancel) # Enable the closing of dialog when the loading is successful.
        else:

            self.progress_label.config(text="File Loading Complete!")
            self.after(500, self.destroy)


class MultiReferenceDialog(tk.Toplevel):
    """
    Modal dialog for editing a multi-value reference collection.
    """

    def __init__(self, parent, current_refs, all_candidates):
        super().__init__(parent)
        self.transient(parent)
        self.title("Edit References")
        self.geometry("500x360")
        self.resizable(True, True)
        self.result = None  # None = cancelled, otherwise (to_add, to_remove)
        self._original = list(current_refs)
        self._all_candidates = all_candidates
        self._iid_to_node = {}   # tree row iid -> node
        self._pending_iid = None  # iid of the placeholder row being edited
        self._add_combo = None
        self._add_var = None
        self._add_filtered = []
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.grab_set()
        self._position_center()
        self.wait_window(self)

    def _create_widgets(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill='both', expand=True)

        # References list
        ref_frame = ttk.LabelFrame(main, text="References")
        ref_frame.pack(fill='both', expand=True, pady=(0, 5))
        ref_frame.rowconfigure(0, weight=1)
        ref_frame.columnconfigure(0, weight=1)

        self._tree = ttk.Treeview(ref_frame, show='tree', selectmode='browse')
        self._tree.tag_configure('proxy', foreground='red')  # references which cannot be resolved
        vsb = ttk.Scrollbar(ref_frame, orient='vertical', command=self._tree.yview)
        hsb = ttk.Scrollbar(ref_frame, orient='horizontal', command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky='nsew', padx=(5, 0), pady=(5, 0))
        vsb.grid(row=0, column=1, sticky='ns', pady=(5, 0), padx=(0, 5))
        hsb.grid(row=1, column=0, sticky='ew', padx=(5, 0), pady=(0, 5))

        for node in self._original:
            iid = self._tree.insert('', 'end', text=node.autosar_path, tags=('proxy',) if node.is_proxy() else ())
            self._iid_to_node[iid] = node

        # + / − buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(0, 5))
        ttk.Button(btn_frame, text="+", width=3, command=self._on_add).pack(side='left', padx=(0, 3))
        ttk.Button(btn_frame, text="\u2212", width=3, command=self._on_remove).pack(side='left')

        # OK / Cancel
        ok_frame = ttk.Frame(main)
        ok_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(ok_frame, text="OK", command=self._on_ok).pack(side='right', padx=5)
        ttk.Button(ok_frame, text="Cancel", command=self._on_cancel).pack(side='right')

    def _on_add(self):
        self._cancel_pending()

        current_paths = {n.autosar_path for n in self._iid_to_node.values()}
        self._add_filtered = [n for n in self._all_candidates if n.autosar_path not in current_paths]
        if not self._add_filtered:
            messagebox.showinfo("No More References", "All available references are already added.", parent=self)
            return

        self._pending_iid = self._tree.insert('', 'end', text='')
        self._tree.see(self._pending_iid)
        self.update_idletasks()
        self._show_add_combo()

    def _show_add_combo(self):
        bbox = self._tree.bbox(self._pending_iid)
        if not bbox:
            self._cancel_pending()
            return
        x, y, _, height = bbox
        width = self._tree.winfo_width() - x - 4

        self._add_var = tk.StringVar()
        combo = ttk.Combobox(self._tree, textvariable=self._add_var, state='normal',
                             values=[n.autosar_path for n in self._add_filtered])
        combo.place(x=x, y=y, width=width, height=height)
        combo.focus_set()
        combo.event_generate('<Button-1>')
        self._add_combo = combo

        self._add_var.trace_add('write', self._on_combo_filter)
        combo.bind('<<ComboboxSelected>>', lambda e: self.after_idle(self._commit_add))
        combo.bind('<Return>', lambda e: self.after_idle(self._commit_add))
        combo.bind('<Escape>', lambda e: self._cancel_pending())
        combo.bind('<FocusOut>', self._on_combo_focus_out)

    def _on_combo_filter(self, *args):
        if self._add_combo is None:
            return
        text = self._add_var.get().lower()
        current_paths = {n.autosar_path for n in self._iid_to_node.values()}
        self._add_filtered = [
            n for n in self._all_candidates
            if n.autosar_path not in current_paths and (not text or text in n.autosar_path.lower())
        ]
        self._add_combo['values'] = [n.autosar_path for n in self._add_filtered]

    def _on_combo_focus_out(self, event):
        # Use after() to let the Combobox dropdown receive focus first
        self.after(50, self._maybe_cancel_on_focus_out)

    def _maybe_cancel_on_focus_out(self):
        if self._add_combo is None:
            return
        if self.focus_get() is self._add_combo:
            return
        self._cancel_pending()

    def _commit_add(self):
        if self._add_combo is None or self._pending_iid is None:
            return
        text = self._add_combo.get()
        matched = [n for n in self._add_filtered if n.autosar_path == text]

        pending_iid = self._pending_iid
        combo = self._add_combo
        self._add_combo = None
        self._pending_iid = None
        combo.destroy()

        if not matched:
            self._tree.delete(pending_iid)
            return

        node = matched[0]
        self._iid_to_node[pending_iid] = node
        self._tree.item(pending_iid, text=node.autosar_path)

    def _cancel_pending(self):
        if self._add_combo is not None:
            self._add_combo.destroy()
            self._add_combo = None
        if self._pending_iid is not None:
            self._tree.delete(self._pending_iid)
            self._pending_iid = None

    def _on_remove(self):
        for iid in self._tree.selection():
            self._iid_to_node.pop(iid, None)
            self._tree.delete(iid)

    def _on_ok(self):
        current_nodes = list(self._iid_to_node.values())
        original_ids = {id(n) for n in self._original}
        current_ids = {id(n) for n in current_nodes}
        to_add = [n for n in current_nodes if id(n) not in original_ids]
        to_remove = [n for n in self._original if id(n) not in current_ids]
        self.result = (to_add, to_remove)
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _position_center(self):
        self.update_idletasks()
        parent = self.master
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f'+{x}+{y}')
