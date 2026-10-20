"""
Example to show how to work with model elements which are split across several files (atpSplitable).
"""
import os, sys
mod_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, mod_path)
from autosarfactory import autosarfactory


def short(path):
    return os.path.basename(path)


def ports_per_file(files):
    """
    Reads every file on its own and returns {file name: [port names of /Swcs/asw1]}, to see what is really saved.
    """
    result = {}
    for file in files:
        autosarfactory.reinit()
        autosarfactory.read([file])
        result[short(file)] = sorted(p.name for p in autosarfactory.get_node('/Swcs/asw1').get_ports())
    autosarfactory.reinit()
    return result


generatedDir = os.path.join(os.path.dirname(__file__), 'generated', 'split_files')
os.makedirs(generatedDir, exist_ok=True)
file1 = os.path.join(generatedDir, 'componentSwc_1.arxml')
file2 = os.path.join(generatedDir, 'componentSwc_2.arxml')

# Two files which both define the package 'Swcs' with the component 'asw1'. Each file holds its own port.
swcs = autosarfactory.new_file(file1, defaultArPackage='Swcs', overWrite=True)
swcs.new_ApplicationSwComponentType('asw1').new_PPortPrototype('portInFile1')
autosarfactory.save()
autosarfactory.reinit()

swcs = autosarfactory.new_file(file2, defaultArPackage='Swcs', overWrite=True)
swcs.new_ApplicationSwComponentType('asw1').new_RPortPrototype('portInFile2')
autosarfactory.save()
autosarfactory.reinit()

# Read both files. There is a single asw1 in the model, with the content of both files.
autosarfactory.read([file1, file2])
asw1 = autosarfactory.get_node('/Swcs/asw1')
print('ports of the merged asw1        :', sorted(p.name for p in asw1.get_ports()))

# Which files contribute to the element? A property, and the same as a list.
print('contributing_files              :', sorted(short(f) for f in asw1.contributing_files))
print('get_fragment_files()            :', sorted(short(f) for f in asw1.get_fragment_files()))

# An element which is defined in one file only is its own single fragment.
port1 = autosarfactory.get_node('/Swcs/asw1/portInFile1')
print('contributing_files of a port    :', sorted(short(f) for f in port1.contributing_files))

# A fragment is the part of the element which lives in one file.
fragment2 = asw1.get_fragment(file2)
print('ports of the fragment of file 2 :', sorted(p.name for p in fragment2.get_ports()))
print('fragment for a file which does not contribute:', asw1.get_fragment(os.path.join(generatedDir, 'other.arxml')))

# Create a port through the fragment: it belongs to file 2, and is also visible on the merged element.
newPort = fragment2.new_PPortPrototype('newPortInFile2')
print('new port belongs to             :', short(newPort.file))
print('ports of the merged asw1 now    :', sorted(p.name for p in asw1.get_ports()))

# Removing works the same way: remove a port of file 1 through the fragment of file 1.
fragment1 = asw1.get_fragment(file1)
fragment1.remove_port(fragment1.get_ports()[0])
print('ports of the merged asw1 after removing the port of file 1:', sorted(p.name for p in asw1.get_ports()))

# Contents are only updated to the files they belong to.
autosarfactory.save()

# Read the files again and see if the expectation is correct.
print('content of each file after save :')
for fileName, ports in ports_per_file([file1, file2]).items():
    print('  %-20s %s' % (fileName, ports))
