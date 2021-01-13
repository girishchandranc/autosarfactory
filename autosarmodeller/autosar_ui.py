import tkinter as tk
import tkinter.ttk as ttk
import os,itertools
from .autosarmodeller import AutosarNode

__resourcesDir__ = os.path.join(os.path.dirname(__file__), 'resources')

class Application(tk.Frame):
    def __init__(self, root, autosar_root):
        self.__root = root
        self.__asr_explorer = None
        self.__property_view = None
        self.__asr_img = tk.PhotoImage(file=os.path.join(__resourcesDir__, 'autosar.png'))
        self.__initialize_ui()
        self.__id_to_node_dict = {}
        #root.attributes('-zoomed', True)
        self.__populate_tree(autosar_root)
 
    def __initialize_ui(self):
        # Configure the root object for the Application
        self.__root.iconphoto(True, self.__asr_img)
        self.__root.title("Autosar Visualizer")
        self.__root.minsize(width=800, height=600)

        # styling
        style = ttk.Style()
        #style.configure('Treeview', background='yellow', foreground='black', fieldbackground='silver', rowheight=25)

        # create ui components
        splitter = tk.PanedWindow(orient=tk.VERTICAL)

        left_frame = tk.Frame(splitter)
        # Create the autosar explorer
        self.__asr_explorer = ttk.Treeview(left_frame, columns=('Type'))
        # Set the heading (Attribute Names)
        self.__asr_explorer.heading('#0', text='Element')
        self.__asr_explorer.heading('#1', text='Type')
        # Specify attributes of the columns (We want to stretch it!)
        self.__asr_explorer.column('#0', stretch=tk.YES)
        self.__asr_explorer.column('#1', stretch=tk.YES)

        # Add scroll bars
        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self.__asr_explorer.yview)
        hsb = ttk.Scrollbar(left_frame, orient="horizontal", command=self.__asr_explorer.xview)

        right_frame = tk.Frame(splitter)
        # Create the properties tree
        self.__property_view = ttk.Treeview(right_frame, columns=('Value'))
        # Set the heading (Attribute Names)
        self.__property_view.heading('#0', text='Property')
        self.__property_view.heading('#1', text='Value')
        self.__property_view.column('#0', stretch=tk.YES)
        self.__property_view.column('#1', stretch=tk.YES)
        # Add scroll bars
        vsb1 = ttk.Scrollbar(right_frame, orient="vertical", command=self.__property_view.yview)
        hsb1 = ttk.Scrollbar(right_frame, orient="horizontal", command=self.__property_view.xview)

        # configure the explorer
        self.__asr_explorer.tag_configure('oddrow', background='#E8E8E8')
        self.__asr_explorer.tag_configure('evenrow', background='#DFDFDF')
        self.__property_view.tag_configure('oddrow', background='#E8E8E8')
        self.__property_view.tag_configure('evenrow', background='#DFDFDF')
        self.__asr_explorer.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.__property_view.configure(yscrollcommand=vsb1.set, xscrollcommand=hsb1.set)

        # layout
        splitter.add(left_frame)
        splitter.add(right_frame)
        splitter.pack(fill=tk.BOTH, expand=1)

        # left-side layout
        self.__asr_explorer.grid(row=0, column=0, sticky='NSEW')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        # right-side layout
        self.__property_view.grid(row=0, column=0, sticky='NSEW')
        vsb1.grid(row=0, column=1, sticky='ns')
        hsb1.grid(row=1, column=0, sticky='ew')
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        
        # bind tree for:
        # selection
        self.__asr_explorer.bind("<Button-1>", self.__on_selection)
        self.__asr_explorer.bind("<Up>", self.__on_selection)
        self.__asr_explorer.bind("<Down>", self.__on_selection)
        #right-click
        self.__asr_explorer.bind("<Button-3>", self.__on_right_click)
        self.__property_view.bind("<Button-3>", self.__on__properties_view_right_click)


    def __on_right_click(self,event):
        # find entry
        item = self.__asr_explorer.identify('item',event.x,event.y)


    def __on__properties_view_right_click(self,event):
        # find entry
        item = self.__property_view.identify('item',event.x,event.y)


    def __on_selection(self, event):
        # find entry
        item = self.__asr_explorer.identify('item',event.x,event.y)
        self.__show_properties(self.__id_to_node_dict[int(item)])


    def __show_properties(self, node):
        # clear old properties tree values first
        self.__property_view.delete(*self.__property_view.get_children())
        # Add new values
        id = 1
        for name,value in node.get_property_values().items():
            tag = "oddrow"
            if id%2==0:
                tag = "evenrow"
            propertyValue = ''
            if isinstance(value, set):
                if len(value) > 0:
                    propertyValue = '['
                    for v in value:
                        propertyValue = propertyValue + str(value) if value is not None else '' + ','
                    propertyValue = propertyValue + ']'
            else:
                propertyValue = str(value) if value is not None else ''

            self.__property_view.insert('', 
                                        "end", 
                                        text=name, 
                                        values=(propertyValue),
                                        tags=(tag))
            id +=1



    def __populate_tree(self, autosar_root):
        idCounter = itertools.count()
        id = next(idCounter)
        tag = "oddrow"
        if id%2==0:
            tag = "evenrow"
        rootTree = self.__asr_explorer.insert('', 'end', iid=id, text="Root", values=('AUTOSAR'), tags=(tag) )
        self.__id_to_node_dict[id] = autosar_root
        self.__add_child(autosar_root, rootTree, idCounter)


    def __add_child(self, node, rootTree, idCounter):
        for child in node.get_children():
            childTree = self.__create_tree_item(child, rootTree, idCounter)
            # add child nodes
            self.__add_child(child, childTree, idCounter)

            # Add referencedby nodes
            if len(child.referenced_by) > 0:
                id = next(idCounter)
                tag = "oddrow"
                if id%2==0:
                    tag = "evenrow"
                referencedByTree = self.__asr_explorer.insert(rootTree, 
                                    "end", 
                                    iid=next(idCounter), 
                                    text="REFERRED_BY", 
                                    values=(''),
                                    tags=(tag))
                for refer_node in child.referenced_by:
                    referTree = self.__create_tree_item(refer_node, referencedByTree, idCounter)
                    # add child nodes of refererred node
                    self.__add_child(refer_node, referTree, idCounter)


    def __create_tree_item(self, node, parentItem, idCounter):
        id = next(idCounter)
        tag = "oddrow"
        if id%2==0:
            tag = "evenrow"
        self.__id_to_node_dict[id] = node
        return self.__asr_explorer.insert(parentItem, 
                                    "end", 
                                    iid=id,
                                    text=node.name if node.name is not None else node.__class__.__name__, 
                                    values=(str(node)),
                                    tags=(tag))


def show_in_ui(autosarRoot):
    win = tk.Tk()
    Application(win, autosarRoot)
    win.mainloop()
