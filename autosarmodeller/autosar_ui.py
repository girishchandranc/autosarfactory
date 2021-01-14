from enum import Enum
import tkinter as tk
import tkinter.ttk as ttk
import os,itertools
from .autosarmodeller import AutosarNode, Referrable

__resourcesDir__ = os.path.join(os.path.dirname(__file__), 'resources')

class Application(tk.Frame):
    def __init__(self, root, autosar_root):
        self.__root = root
        self.__asr_explorer = None
        self.__property_view = None
        self.__referred_by_view = None
        self.__search_field = None
        self.__search_view = None
        self.__go_to_menu = None
        self.__asr_img = tk.PhotoImage(file=os.path.join(__resourcesDir__, 'autosar.png'))
        self.__initialize_ui()
        self.__asr_explorer_id_to_node_dict = {}
        self.__asr_explorer_node_to_id_dict = {} # reverse of the above dict for a faster lookup.
        self.__referred_by_view_id_to_node_dict = {}
        self.__property_view_id_to_node_dict = {}
        self.__search_view_id_to_node_dict = {}
        self.__go_to_node_id_in_asr_explorer = None
        self.__root_tree = None
        #root.attributes('-zoomed', True)
        self.__populate_tree(autosar_root)
 
    def __initialize_ui(self):
        # Configure the root object for the Application
        self.__root.iconphoto(True, self.__asr_img)
        self.__root.title("Autosar Visualizer")
        self.__root.minsize(width=800, height=600)

        # set theme
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview",
                background="#E1E1E1",
                foreground="#000000",
                rowheight=20,
                fieldbackground="#E1E1E1")
        # set backgound and foreground color when selected
        style.map('Treeview', background=[('selected', '#BFBFBF')], foreground=[('selected', 'black')])

        # create ui components
        splitter = tk.PanedWindow(orient=tk.VERTICAL)
        top_frame = tk.Frame(splitter)

        # Create the autosar explorer
        self.__asr_explorer = ttk.Treeview(top_frame, columns=('Type'))
        # Set the heading (Attribute Names)
        self.__asr_explorer.heading('#0', text='Element')
        self.__asr_explorer.heading('#1', text='Type')
        # Specify attributes of the columns (We want to stretch it!)
        self.__asr_explorer.column('#0', stretch=tk.YES, minwidth=100, width = 100)
        self.__asr_explorer.column('#1', stretch=tk.YES, minwidth=100, width = 100)

        # Add scroll bars
        vsb = ttk.Scrollbar(top_frame, orient="vertical", command=self.__asr_explorer.yview)
        hsb = ttk.Scrollbar(top_frame, orient="horizontal", command=self.__asr_explorer.xview)

        bottom_frame = tk.Frame(splitter)
        # Create the properties tree
        self.__property_view = ttk.Treeview(bottom_frame, columns=('Value'))
        # Set the heading (Attribute Names)
        self.__property_view.heading('#0', text='Property')
        self.__property_view.heading('#1', text='Value')
        self.__property_view.column('#0', stretch=tk.YES, minwidth=50)
        self.__property_view.column('#1', stretch=tk.YES, minwidth=50)
        # Add scroll bars
        vsb1 = ttk.Scrollbar(bottom_frame, orient="vertical", command=self.__property_view.yview)
        hsb1 = ttk.Scrollbar(bottom_frame, orient="horizontal", command=self.__property_view.xview)

        # Create the referred_by tree
        self.__referred_by_view = ttk.Treeview(bottom_frame)
        # Set the heading (Attribute Names)
        self.__referred_by_view.heading('#0', text='Referenced By')
        self.__referred_by_view.column('#0', stretch=tk.YES, minwidth=100)
        # Add scroll bars
        vsb2 = ttk.Scrollbar(bottom_frame, orient="vertical", command=self.__referred_by_view.yview)
        hsb2 = ttk.Scrollbar(bottom_frame, orient="horizontal", command=self.__referred_by_view.xview)

        # create the search view
        search_frame = ttk.Frame(bottom_frame)
        self.__search_field = ttk.Entry(search_frame)
        self.__search_field.insert(0, 'search')
        #go_button = ttk.Button(search_frame, text='Go', command=self.__on_next_button_click)
        self.__search_view = ttk.Treeview(search_frame)
        # Set the heading (Attribute Names)
        self.__search_view.heading('#0', text='Results')
        self.__search_view.column('#0', stretch=tk.YES, minwidth=100)
        # Add scroll bars
        vsb3 = ttk.Scrollbar(search_frame, orient="vertical", command=self.__search_view.yview)
        hsb3 = ttk.Scrollbar(search_frame, orient="horizontal", command=self.__search_view.xview)

        # configure the explorer
        self.__search_field.config(foreground='grey')
        self.__asr_explorer.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.__property_view.configure(yscrollcommand=vsb1.set, xscrollcommand=hsb1.set)
        self.__referred_by_view.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        self.__search_view.configure(yscrollcommand=vsb3.set, xscrollcommand=hsb3.set)

        # layout
        splitter.add(top_frame)
        splitter.add(bottom_frame)
        splitter.pack(fill=tk.BOTH, expand=1)

        # top layout
        self.__asr_explorer.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        top_frame.rowconfigure(0, weight=1)
        top_frame.columnconfigure(0, weight=1)

        # bottom layout
        self.__property_view.grid(row=0, column=0, sticky='NSEW')
        vsb1.grid(row=0, column=1, sticky='ns')
        hsb1.grid(row=1, column=0, sticky='ew')
        self.__referred_by_view.grid(row=0, column=2, sticky='NSEW')
        vsb2.grid(row=0, column=3, sticky='ns')
        hsb2.grid(row=1, column=2, sticky='ew')
        search_frame.grid(row=0, column=4, sticky='nsew')
        self.__search_field.grid(row=0, column=3, sticky='nsew')
        self.__search_view.grid(row=2, column=3, sticky='nsew')
        vsb3.grid(row=2, column=4, sticky='ns')
        hsb3.grid(row=3, column=3, sticky='ew')

        search_frame.rowconfigure(2, weight=1)
        search_frame.columnconfigure(4, weight=1)

        bottom_frame.rowconfigure(0, weight=1)
        bottom_frame.columnconfigure(0, weight=1)

        ##create menu items
        self.__go_to_menu = tk.Menu(self.__root, tearoff=0)
        self.__go_to_menu.add_command(label='Go to item', command=self.__go_to_node_in_asr_explorer)

        # bind search entry
        self.__search_field.bind('<FocusIn>', self.__on_search_entry_click)
        self.__search_field.bind('<FocusOut>', self.__on_search_entry_focusout)
        self.__search_field.bind('<Return>', self.__on_search_entry_click)

        # bind tree for:
        # selection
        self.__asr_explorer.bind("<Button-1>", self.__on_selection)
        self.__search_view.bind("<Button-1>", self.__on_search_view_selection)

        #right-click
        self.__referred_by_view.bind("<Button-3>", self.__on_referred_by_view_right_click)
        self.__property_view.bind("<Button-3>", self.__on__properties_view_right_click)


    def __on_search_entry_click(self, event):
        search_string = self.__search_field.get()
        if search_string == 'search':
            self.__search_field.delete(0, "end") # delete all the text in the entry
            self.__search_field.insert(0, '') #Insert blank for user input
            self.__search_field.config(foreground='black')
        elif search_string != '':
            search_nodes = []
            for node in self.__asr_explorer_id_to_node_dict.values():
                if node.name is not None and search_string.lower() in node.name.lower():
                    search_nodes.append(node)
            self.__update_search_view(search_nodes)
        else:
            self.__update_search_view([])


    def __on_search_entry_focusout(self,event):
        if self.__search_field.get() == '':
            self.__search_field.insert(0, 'search')
            self.__search_field.config(foreground='grey')


    def __on_referred_by_view_right_click(self,event):
        # find entry
        item = self.__referred_by_view.identify('item',event.x,event.y)
        if item != '':
            self.__go_to_node_id_in_asr_explorer = self.__asr_explorer_node_to_id_dict[self.__referred_by_view_id_to_node_dict[int(item)]]
            self.__go_to_menu.tk_popup(event.x_root, event.y_root, 0)


    def __on__properties_view_right_click(self,event):
        # find entry
        item = self.__property_view.identify('item',event.x,event.y)
        if item != '' and int(item) in self.__property_view_id_to_node_dict:
            self.__go_to_node_id_in_asr_explorer = self.__asr_explorer_node_to_id_dict[self.__property_view_id_to_node_dict[int(item)]]
            self.__go_to_menu.tk_popup(event.x_root, event.y_root, 0)


    def __go_to_node_in_asr_explorer(self):
        if self.__go_to_node_id_in_asr_explorer is not None:
            self.__open_node(self.__asr_explorer.parent(self.__go_to_node_id_in_asr_explorer))
            self.__asr_explorer.selection_set(self.__go_to_node_id_in_asr_explorer)
            self.__asr_explorer.focus(self.__go_to_node_id_in_asr_explorer)
            self.__asr_explorer.see(self.__go_to_node_id_in_asr_explorer)

            # Update the views
            node = self.__asr_explorer_id_to_node_dict[int(self.__go_to_node_id_in_asr_explorer)]
            self.__update_properties_view(node)
            self.__update_referred_by_view(node)


    def __open_node(self, id):
        parent_id = self.__asr_explorer.parent(id)
        if parent_id != '':
            self.__open_node(parent_id)
        self.__asr_explorer.item(id, open=True)


    def __on_selection(self, event):
        # find entry
        item = self.__asr_explorer.identify('item',event.x,event.y)
        if item != '':
            node = self.__asr_explorer_id_to_node_dict[int(item)]
            self.__update_properties_view(node)
            self.__update_referred_by_view(node)


    def __on_search_view_selection(self, event):
        # find entry
        item = self.__search_view.identify('item',event.x,event.y)
        if item != '':
            self.__go_to_node_id_in_asr_explorer = self.__asr_explorer_node_to_id_dict[self.__search_view_id_to_node_dict[int(item)]]
            self.__go_to_node_in_asr_explorer()


    def __update_properties_view(self, node):
        # clear old properties tree values first
        self.__property_view.delete(*self.__property_view.get_children())
        self.__property_view_id_to_node_dict.clear()

        # Add new values
        id = 1
        for name,value in node.get_property_values().items():
            propertyValue = ''
            if isinstance(value, set):
                if len(value) > 0:
                    propertyValue = '['
                    for v in value:
                        propertyValue = propertyValue + str(value) if value is not None else '' + ','
                    propertyValue = propertyValue + ']'
            elif isinstance(value,Enum):
                propertyValue = value.literal if value is not None else ''
            else:
                propertyValue = str(value) if value is not None else ''
                if isinstance(value, Referrable):
                    self.__property_view_id_to_node_dict[id] = value

            self.__property_view.insert('', 
                                        "end", 
                                        iid=id,
                                        text=name, 
                                        values=(propertyValue))
            id +=1


    def __update_search_view(self, nodes):
        # clear old search tree values first
        self.__search_view.delete(*self.__search_view.get_children())
        self.__search_view_id_to_node_dict.clear()

        # Add new values
        id = 1
        for node in nodes:
            self.__search_view.insert('', 
                                        "end", 
                                        iid=id,
                                        text=str(node))
            self.__search_view_id_to_node_dict[id] = node
            id +=1


    def __update_referred_by_view(self, node):
        # clear old tree values first
        self.__referred_by_view.delete(*self.__referred_by_view.get_children())
        self.__referred_by_view_id_to_node_dict.clear()

        id = 1
        for ref in node.referenced_by:
            self.__referred_by_view.insert('', 
                                    "end", 
                                    iid=id,
                                    text=(str(ref)))
            self.__referred_by_view_id_to_node_dict[id] = ref
            id += 1


    def __populate_tree(self, autosar_root):
        idCounter = itertools.count()
        id = next(idCounter)
        self.__root_tree = self.__asr_explorer.insert('', 'end', iid=id, text="AutosarRoot", values=('AUTOSAR'))
        self.__asr_explorer_id_to_node_dict[id] = autosar_root
        self.__asr_explorer_node_to_id_dict[autosar_root] = id
        self.__add_child(autosar_root, self.__root_tree, idCounter)


    def __add_child(self, node, parentItem, idCounter):
        for child in node.get_children():
            childTree = self.__create_tree_item(child, parentItem, idCounter)
            # add child nodes
            self.__add_child(child, childTree, idCounter)


    def __create_tree_item(self, node, parentItem, idCounter):
        id = next(idCounter)
        self.__asr_explorer_id_to_node_dict[id] = node
        self.__asr_explorer_node_to_id_dict[node] = id
        return self.__asr_explorer.insert(parentItem, 
                                    "end", 
                                    iid=id,
                                    text=node.name if node.name is not None else node.__class__.__name__, 
                                    values=(str(node)))


def show_in_ui(autosarRoot):
    win = tk.Tk()
    Application(win, autosarRoot)
    win.mainloop()
