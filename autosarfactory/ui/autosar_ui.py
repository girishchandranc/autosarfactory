import tkinter as tk
import tkinter.font as tkFont
import os
from tkinter import Menu, ttk, messagebox
import sv_ttk
from configparser import ConfigParser
from pathlib import Path
from autosarfactory import autosarfactory

from .dialogs import LoadModelsDialog
from .explorer import ARExplorer
from .property_view import PropertyView
from .search import Search

__resourcesDir__ = os.path.join(os.path.dirname(__file__), 'resources')
__PAD_X__ = 5 # For some additional padding in the column width


class Application(ARExplorer, PropertyView, Search, tk.Frame):

    def __init__(self, root):
        self._root = root
        self._asr_explorer = None
        self._property_view = None
        self._referred_by_view = None
        self._search_dropdown = None
        self._search_field = None
        self._search_view = None
        self._search_results_label = None
        self._referenced_by_label = None
        self._go_to_menu = None
        self._asr_explorer_menu = None
        self._dialog = None
        self._asr_img = tk.PhotoImage(file=os.path.join(__resourcesDir__, 'autosar.png'))
        self.__initialize_ui()
        self._asr_explorer_id_to_node_dict = {}
        self._asr_explorer_node_to_id_dict = {} # reverse of the above dict for a faster lookup.
        self._referred_by_view_id_to_node_dict = {}
        self._property_view_id_to_node_dict = {}
        self._search_view_id_to_node_dict = {}
        self._go_to_node_id_in_asr_explorer = None
        self._font__ = tkFont.nametofont('TkHeadingFont')

        # Inline property editing state
        self._property_view_id_to_edit_meta: dict = {}  # iid -> (prop_name, type, enum_class|None)
        self._property_view_current_node = None          # node currently shown in property view
        self._has_unsaved_changes: bool = False
        self._active_editor = None                       # live Entry or Combobox widget
        self._editing_iid = None                         # row iid being edited
        self._ref_popup = None                           # Toplevel dropdown for ref editing
        self._ref_listbox = None                         # Listbox inside ref popup
        self._ref_candidates: list = []                  # full candidate list
        self._ref_filtered: list = []                    # currently shown candidates

    def __initialize_ui(self):
        # Configure the root object for the Application
        self._root.iconphoto(True, self._asr_img)
        self._root.title("Autosar Viewer")
        self._root.minsize(width=800, height=600)

        # create ui components
        menubar = Menu(self._root)
        filemenu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=filemenu)
        filemenu.add_command(label="Load Models...", command=self._open_load_dialog)
        filemenu.add_command(label="Save", command=self._save, accelerator="Ctrl+S")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=lambda: self._client_exit(self._root))
        self._root.bind_all("<Control-s>", lambda event: self._save())

        thememenu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Select Theme", menu=thememenu)
        thememenu.add_command(label="Light", command=lambda: sv_ttk.set_theme('light'))
        thememenu.add_command(label="Dark", command=lambda: sv_ttk.set_theme('dark'))
        self._root.config(menu=menubar)

        splitter = tk.PanedWindow(orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=5)
        self._splitter = splitter
        top_frame = tk.Frame(splitter)

        # Create the autosar explorer
        self._asr_explorer = ttk.Treeview(top_frame, columns=('Type'))
        # Set the heading (Attribute Names)
        self._asr_explorer.heading('#0', text='Element')
        self._asr_explorer.heading('#1', text='Type')
        # Specify attributes of the columns (We want to stretch it!)
        self._asr_explorer.column('#0', stretch=tk.YES, minwidth=100, width=0)
        self._asr_explorer.column('#1', stretch=tk.YES, minwidth=100, width=0)

        # Add scroll bars
        vsb = ttk.Scrollbar(top_frame, orient="vertical", command=self._asr_explorer.yview)
        hsb = ttk.Scrollbar(top_frame, orient="horizontal", command=self._asr_explorer.xview)

        bottom_frame = tk.Frame(splitter)
        # Create the properties tree
        self._property_view = ttk.Treeview(bottom_frame, columns=('Value'))

        # Set the heading (Attribute Names)
        self._property_view.heading('#0', text='Property')
        self._property_view.heading('#1', text='Value')
        self._property_view.column('#0', stretch=tk.YES, minwidth=150)
        self._property_view.column('#1', stretch=tk.YES, minwidth=150)

        # Add scroll bars
        vsb1 = ttk.Scrollbar(bottom_frame, orient="vertical", command=self._property_view.yview)
        hsb1 = ttk.Scrollbar(bottom_frame, orient="horizontal", command=self._property_view.xview)

        # Create the referred_by tree
        referenced_by_frame = ttk.Frame(bottom_frame)
        self._referenced_by_label = ttk.Label(referenced_by_frame, text="Referenced By")
        self._referred_by_view = ttk.Treeview(referenced_by_frame, show="tree")
        self._referred_by_view.column('#0', stretch=tk.YES, minwidth=50)
        # Add scroll bars
        vsb2 = ttk.Scrollbar(referenced_by_frame, orient="vertical", command=self._referred_by_view.yview)
        hsb2 = ttk.Scrollbar(referenced_by_frame, orient="horizontal", command=self._referred_by_view.xview)

        # create the search view
        search_frame = ttk.Frame(bottom_frame)
        self._search_type = ttk.Label(search_frame, text="Search Type")
        self._search_dropdown = ttk.Combobox(search_frame, state="readonly", values=["Short Name","Autosar Type","Regular Expression"])
        self._search_field = ttk.Entry(search_frame)
        self._search_field.insert(0, 'search')
        self._search_results_label = ttk.Label(search_frame, text="Results")
        self._search_view = ttk.Treeview(search_frame, show="tree")
        self._search_view.column('#0', stretch=tk.YES, minwidth=50)

        # Add scroll bars
        vsb3 = ttk.Scrollbar(search_frame, orient="vertical", command=self._search_view.yview)
        hsb3 = ttk.Scrollbar(search_frame, orient="horizontal", command=self._search_view.xview)

        # configure the explorer
        self._search_field.config(foreground='grey')
        self._asr_explorer.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._property_view.configure(yscrollcommand=vsb1.set, xscrollcommand=hsb1.set)
        self._referred_by_view.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        self._search_view.configure(yscrollcommand=vsb3.set, xscrollcommand=hsb3.set)

        # layout
        splitter.add(top_frame, stretch='always')
        splitter.add(bottom_frame, stretch='always')
        splitter.pack(fill=tk.BOTH, expand=1)

        # top layout
        self._asr_explorer.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        # top_frame.rowconfigure(1, weight=1)
        top_frame.rowconfigure(0, weight=1)
        top_frame.columnconfigure(0, weight=1)

        # bottom layout
        self._property_view.grid(row=0, column=0, sticky='nsew')
        vsb1.grid(row=0, column=1, sticky='ns')
        hsb1.grid(row=1, column=0, sticky='ew')

        # referenced_by layout
        referenced_by_frame.grid(row=0, column=2, sticky='nsew')
        self._referenced_by_label.grid(row=0, column=2, sticky='ew')
        self._referred_by_view.grid(row=1, column=2, sticky='nsew')
        vsb2.grid(row=1, column=3, sticky='ns')
        hsb2.grid(row=2, column=2, sticky='ew')
        referenced_by_frame.rowconfigure(1, weight=1)
        referenced_by_frame.columnconfigure(2, weight=1)

        # search frame layout
        search_frame.grid(row=0, column=4, sticky='nsew')
        self._search_type.grid(row=0, column=3, sticky='ew')
        self._search_dropdown.grid(row=0, column=4, sticky='ew')
        self._search_dropdown.current(0)
        self._search_field.grid(row=1, column=3, columnspan=2, sticky='ew')
        self._search_results_label.grid(row=2, column=3, sticky='ew', columnspan=2)
        self._search_view.grid(row=3, column=3, sticky='nsew', columnspan=2)
        vsb3.grid(row=3, column=5, sticky='ns')
        hsb3.grid(row=5, column=3, sticky='ew', columnspan=2)
        search_frame.rowconfigure(3, weight=1)
        search_frame.columnconfigure(5, weight=1)

        bottom_frame.rowconfigure(0, weight=1)
        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(2, weight=1)

        # create menu items
        self._go_to_menu = tk.Menu(self._root, tearoff=0)
        self._go_to_menu.add_command(label='Go to item', command=self._go_to_node_in_asr_explorer)
        self._asr_explorer_menu = tk.Menu(self._root, tearoff=0)
        self._asr_explorer_menu.add_command(label='New...', command=self._open_new_element_popup)
        self._asr_explorer_menu.add_command(label='Delete', command=self._delete_element)
        self._asr_explorer_menu.add_separator()
        self._asr_explorer_menu.add_command(label='Generate Graph', command=self._generate_graph)
        self._asr_explorer_menu.add_command(label='Copy ShortName', command=self._copy_name_to_clip_board)
        self._asr_explorer_menu.add_command(label='Copy AutosarPath', command=self._copy_path_to_clip_board)
        self._asr_explorer_menu.add_command(label='Copy FilePath', command=self._copy_file_path_to_clip_board)

        # bind search entry
        self._search_field.bind('<FocusIn>', self._on_search_entry_click)
        self._search_field.bind('<FocusOut>', self._on_search_entry_focusout)
        self._search_field.bind('<Return>', self._on_search_entry_click)

        # bind tree for:
        # selection
        self._asr_explorer.bind("<Button-1>", self._on_asr_explorer_selection)
        self._asr_explorer.bind("<KeyRelease>", self._on_asr_explorer_key_released)
        self._search_view.bind("<Button-1>", self._on_search_view_selection)
        self._search_view.bind("<KeyRelease>", self._on_search_view_key_released)

        # right-click
        self._referred_by_view.bind("<Button-3>", self._on_referred_by_view_right_click)
        self._property_view.bind("<Button-3>", self._on__properties_view_right_click)
        self._asr_explorer.bind("<Button-3>", self._on__asr_explorer_right_click)

        # inline editing
        self._property_view.bind("<Double-1>", self._on_property_view_double_click)

    def _open_load_dialog(self):
        files = [] if self._dialog is None else self._dialog.selected_paths
        self._dialog = LoadModelsDialog(self._root, files)
        if self._dialog.autosarRoot:
            self._populate_tree(self._dialog.autosarRoot)

    def _client_exit(self, root):
        if self._has_unsaved_changes:
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved changes. Exit without saving?"):
                return
        root.destroy()


def __setup_ui() -> Application:
    win = tk.Tk()
    app = Application(win)

    # read preferences
    pref_file = os.path.join(Path(__file__).resolve().parent, 'AutosarUI_pref.ini')
    config = ConfigParser()
    config.read(pref_file)
    pref_theme = config.get('Appearance', 'theme', fallback='light')
    pref_sash = config.getfloat('Layout', 'sash_ratio', fallback=0.65)

    # set the theme
    sv_ttk.set_theme(pref_theme)

    # set sash position after the window has been rendered and has real dimensions
    def apply_sash():
        h = app._splitter.winfo_height()
        if h > 1:
            app._splitter.sash_place(0, 0, int(h * pref_sash))
        else:
            win.after(50, apply_sash)  # retry if layout not ready yet

    win.after(100, apply_sash)

    def on_destroy(event):
        if event.widget != win:
            return
        # save theme and sash ratio on exit
        try:
            sash_y = app._splitter.sash_coord(0)[1]
            total_h = app._splitter.winfo_height()
            ratio = sash_y / total_h if total_h > 0 else 0.65
        except Exception:
            ratio = 0.65
        config['Appearance'] = {'theme': sv_ttk.get_theme(win)}
        config['Layout'] = {'sash_ratio': str(round(ratio, 4))}
        with open(pref_file, 'w') as f:
            config.write(f)

    win.bind("<Destroy>", on_destroy)
    win.mainloop()
    return app

def main():
    __setup_ui()

main()
