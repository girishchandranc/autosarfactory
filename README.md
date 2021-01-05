[![Build Actions Status](https://github.com/girishchandranc/autosarmodeller/workflows/Build/badge.svg)](https://github.com/girishchandranc/autosarmodeller/actions)
# Autosar Modelling Tool
AutosarModeller provides nice methods to read/create/modify AUTOSAR compliant arxml files.

## Using the package
Simply clone the repo and import the package autosarmodeller to your python file and have fun with modelling AUTOSAR.

### Reading file
```python
files = ['component.arxml', 'datatypes.arxml']
root, status = autosarmodeller.read(files)
```
The read method processes the input files and return the root node(with merged info of all the given files). The status gives an info if the file reading was successful.

### Creating new file
```python
newPack = autosarmodeller.create_new_file('newFile.arxml', defaultArPackage = 'NewPack')
```
Creates a new arxml file with the given package name and returns the ARPackage object.
- If package name is not provided, default package name 'RootPackage' is used. 
- The method raises FileExistsError if the given file already exist. To avoid this, please pass the argument overWrite as True.

### Accessing attributes and references
Model elements have `get_<attribute/reference>` methods to access existing attribute and reference value.
> For multi-references, the method returns a list of values

### Modifying attributes/references
All the elements have `set_<attribute/reference>`methods to modify the attribute or reference value.
> For multi-references, there also exists methods `add_<reference>`, `remove_<reference>`

### Adding new model elements
All the parent classes have `create_<element>` methods to create an element.
```python
rootPack = autosarmodeller.create_new_file('newFile.arxml', defaultArPackage = 'RootPack')
newPack = rootPack.create_ARPackage('NewPack')
#new applicaton component
asw1 = newPack.create_ApplicationSwComponentType('asw1')
asw1.create_PPortPrototype('outPort')

#new senderRecever interface
srIf = newPack.create_SenderReceiverInterface('srif1')
srIf.create_DataElement('de1')
```
### Accessing elements by path
Once the file is read by the tool, its possible to access elements by path.
```python
files = ['component.arxml', 'datatypes.arxml']
autosarmodeller.read(files)
swc = autosarmodeller.get_node('/Swcs/asw1')
uint8DataType = autosarmodeller.get_node('/DataTypes/baseTypes/uint8')
```

### Saving options
#### Save
The tool provides `save` method to save the changes made to the model.
```python
files = ['component.arxml', 'datatypes.arxml']
autosarmodeller.read(files)

rootPack = autosarmodeller.create_new_file('newFile.arxml', defaultArPackage = 'RootPack')
newPack = rootPack.create_ARPackage('NewPack')

#new applicaton component
newcomp = newPack.create_ApplicationSwComponentType('newcomponent')
newcomp.create_PPortPrototype('outPort')

#new senderRecever interface
srIf = newPack.create_SenderReceiverInterface('srif1')
srIf.create_DataElement('de1')

#save changes
autosarmodeller.save(['newFile.arxml'])
```
The `save` method accepts a list of file which needs to be saved. If no argument is provided, all the files(input, newly created) will be saved.

#### SaveAs
The tool provides `saveAs` method to save the changes made to the model into a single arxml file.
```python
files = ['component.arxml', 'datatypes.arxml']
autosarmodeller.read(files)

rootPack = autosarmodeller.create_new_file('newFile.arxml', defaultArPackage = 'RootPack')
newPack = rootPack.create_ARPackage('NewPack')

#new applicaton component
newcomp = newPack.create_ApplicationSwComponentType('newcomponent')
newcomp.create_PPortPrototype('outPort')

#new senderRecever interface
srIf = newPack.create_SenderReceiverInterface('srif1')
srIf.create_DataElement('de1')

#save changes
autosarmodeller.saveAs('mergedFile.arxml')
```

## Examples
Please check the script inside the `Examples`folder which creates a basic communication matrix. 

For more information on the usage, please refer `tests/test_autosarmodel.py`.
