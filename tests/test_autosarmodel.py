import os, sys, shutil
import pytest, filecmp
from lxml import etree

mod_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, mod_path)

from autosarfactory import autosarfactory

resourcesDir = os.path.join(os.path.dirname(__file__), 'resources')

input_files = [os.path.join(resourcesDir, 'components.arxml'), 
               os.path.join(resourcesDir, 'datatypes.arxml'),
               os.path.join(resourcesDir, 'interfaces.arxml'),
               os.path.join(resourcesDir, 'diag_sw_mapping.arxml')]

invalid_files = [os.path.join(resourcesDir, 'invalid.arxml')]

def _create_temp_dir():
    tempDir = os.path.join(resourcesDir,"temp")
    os.makedirs(tempDir, exist_ok=True)
    return tempDir

def teardown(deleteTempDir = True):
    """ teardown any state that was previously setup.
    """
    autosarfactory.reinit()
    assert (autosarfactory.get_root() is None), 'Root should be None'

    if deleteTempDir and os.path.exists(os.path.join(resourcesDir,"temp")):
        shutil.rmtree(os.path.join(resourcesDir,"temp"))

class AutosarModelTestHelper:
    """
    Helpers used by the tests.
    """
    ARXML_HEADER = '<?xml version="1.0" encoding="UTF-8"?><AUTOSAR xmlns="http://autosar.org/schema/r4.0"><AR-PACKAGES>{}</AR-PACKAGES></AUTOSAR>'

    @staticmethod
    def names(nodes):
        """
        Sorted names of the given nodes.
        """
        return sorted(n.name for n in nodes)

    @staticmethod
    def write_arxml(directory, name, packages):
        """
        Writes an arxml file with the given AR-PACKAGE xml snippet(s) and returns its path.
        """
        path = os.path.join(str(directory), name)
        with open(path, 'w') as f:
            f.write(AutosarModelTestHelper.ARXML_HEADER.format(packages))
        return path

    @staticmethod
    def swc_packages(*package_names):
        """
        AR-PACKAGE snippets. The package 'P' holds one application sw component named 'Swc', all others are empty.
        """
        swc = '<ELEMENTS><APPLICATION-SW-COMPONENT-TYPE><SHORT-NAME>Swc</SHORT-NAME></APPLICATION-SW-COMPONENT-TYPE></ELEMENTS>'
        return ''.join('<AR-PACKAGE><SHORT-NAME>{}</SHORT-NAME>{}</AR-PACKAGE>'.format(n, swc if n == 'P' else '') for n in package_names)

    @staticmethod
    def swcs_in_file(file):
        """
        Reads the arxml file manually and returns a list of (swc name, name of the package which holds it).
        """
        tree = etree.parse(file, etree.XMLParser(remove_blank_text=True))
        return [(e.find('{*}SHORT-NAME').text, e.getparent().getparent().find('{*}SHORT-NAME').text)
                for e in tree.findall('.//{*}APPLICATION-SW-COMPONENT-TYPE')]

    @staticmethod
    def write_split_implementation_files(directory):
        """
        Writes two arxml files which both define the same SWC-IMPLEMENTATION /P/Impl.
        SwcImplementation has several containment slots holding the same python type
        (DependencyOnArtifact): generatedArtifacts, requiredArtifacts and requiredGeneratorTools.
        file1 contributes a generated artifact (Gen1) and file2 a required artifact (Req2).
        """
        template = '''<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR xmlns="http://autosar.org/schema/r4.0">
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>P</SHORT-NAME>
      <ELEMENTS>
        <SWC-IMPLEMENTATION>
          <SHORT-NAME>Impl</SHORT-NAME>
          <{tag}>
            <DEPENDENCY-ON-ARTIFACT>
              <SHORT-NAME>{name}</SHORT-NAME>
            </DEPENDENCY-ON-ARTIFACT>
          </{tag}>
        </SWC-IMPLEMENTATION>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>'''
        file1 = os.path.join(str(directory), 'impl1.arxml')
        file2 = os.path.join(str(directory), 'impl2.arxml')
        with open(file1, 'w') as f:
            f.write(template.format(tag='GENERATED-ARTIFACTS', name='Gen1'))
        with open(file2, 'w') as f:
            f.write(template.format(tag='REQUIRED-ARTIFACTS', name='Req2'))
        return file1, file2

    @staticmethod
    def slot_contents(file):
        """
        Parses the arxml file manually and returns the short names of the DEPENDENCY-ON-ARTIFACT elements
        found in each artifact slot of /P/Impl.
        """
        impl_xml = etree.parse(file, etree.XMLParser(remove_blank_text=True)).find('.//{*}SWC-IMPLEMENTATION')
        return {tag: [e.find('{*}SHORT-NAME').text for e in impl_xml.findall('{*}' + tag + '/{*}DEPENDENCY-ON-ARTIFACT')]
                for tag in ('GENERATED-ARTIFACTS', 'REQUIRED-ARTIFACTS', 'REQUIRED-GENERATOR-TOOLS')}


def test_model_load_invalid_input():
    """
    Tests if the model is not loaded when invalid files are passed.
    """
    root, status = autosarfactory.read(invalid_files)
    assert (root is None), 'Root should be None'
    assert (status is False), 'status is False for invalid file'
    teardown()

def test_model_load():
    """
    Tests if the model is properly loaded when arxml files are passed.
    """
    root, status = autosarfactory.read(input_files)
    assert (root is not None), 'Root should not be None'
    assert (status), 'status is True when the file is loaded properly'
    assert (len(root.get_arPackages()) > 0), 'arpackages count should be greater than 0'
    teardown()

def test_model_create_new_file():
    """
    Tests if the new autosar file is properly created.
    """
    packageName = 'myPack_12345'
    filePath = os.path.join(resourcesDir, 'newFile.arxml')

    arPackage = autosarfactory.new_file(filePath,overWrite=True,defaultArPackage=packageName)
    assert (arPackage is not None), 'ArPackage should not be None'
    assert (arPackage.name == packageName), 'ArPackage should be '+ packageName
    assert (os.path.isfile(filePath)), 'File should exist'
    teardown()

def test_model_access():
    """
    Tests if the root node contans the merged entities from all files(input and created).
    """
    root, status = autosarfactory.read(input_files)
    assert (root is not None), 'root should not be None'
    assert (len(root.get_arPackages()) == 4), '4 Ar-packages expected'
    
    swcPackage = next((x for x in root.get_arPackages() if x.name == 'Swcs'), None)
    assert (swcPackage is not None), 'swcPackage should not be None'
    assert (len(swcPackage.get_elements()) == 4), '4 elements expected'

    asw1 = next((x for x in swcPackage.get_elements() if x.name == 'asw1'), None)
    asw2 = next((x for x in swcPackage.get_elements() if x.name == 'asw2'), None)
    Comp = next((x for x in swcPackage.get_elements() if x.name == 'Comp'), None)

    assert (asw1 is not None), 'asw1 should not be None'
    assert(isinstance(asw1, autosarfactory.ApplicationSwComponentType)), 'asw1 should be an instance of ApplicationSwComponentType'
    assert (asw2 is not None), 'asw2 should not be None'
    assert(isinstance(asw2, autosarfactory.ApplicationSwComponentType)), 'asw2 should be an instance of ApplicationSwComponentType'
    assert (Comp is not None), 'Comp should not be None'
    assert(isinstance(Comp, autosarfactory.CompositionSwComponentType)), 'Comp should be an instance of CompositionSwComponentType'

    ifPackage = next((x for x in root.get_arPackages() if x.name == 'Interfaces'), None)
    assert (ifPackage is not None), 'ifPackage should not be None'
    assert (len(ifPackage.get_elements()) == 1), '1 element expected'
    
    srIf = next((x for x in ifPackage.get_elements() if x.name == 'srif1'), None)
    assert (srIf is not None), 'srIf should not be None'
    assert (isinstance(srIf, autosarfactory.SenderReceiverInterface)), 'should be an instance of SenderReceiverInterface'

    assert (len(srIf.get_dataElements()) == 1), '1 element expected'
    vdp = next((x for x in srIf.get_dataElements() if x.name == 'de1'), None)
    assert (vdp is not None), 'vdp should not be None'
    assert (isinstance(vdp, autosarfactory.VariableDataPrototype)), 'should be an instance of VariableDataPrototype'

    teardown()

def test_model_path():
    """
    Tests if the path returns the node.
    """
    autosarfactory.read(input_files)
    asw1 = autosarfactory.get_node('/Swcs/asw1')
    assert (asw1 is not None), 'asw1 should not be None'
    assert(isinstance(asw1, autosarfactory.ApplicationSwComponentType)), 'asw1 should be an instance of ApplicationSwComponentType'
    assert (asw1.name == 'asw1'), 'name should be asw1'

    vdp = autosarfactory.get_node('/Interfaces/srif1/de1')
    assert (vdp is not None), 'vdp should not be None'
    assert(isinstance(vdp, autosarfactory.VariableDataPrototype)), 'vdp should be an instance of VariableDataPrototype'
    assert (vdp.name == 'de1'), 'name should be de1'

    dswm = autosarfactory.get_node('/RootPackage/map1')
    diagDE = dswm.get_diagnosticDataElement()
    assert (diagDE is not None), 'diagDE should not be None'
    assert (diagDE.autosar_path == '/RootPackage/Record1/element1'), 'diagDE path is /RootPackage/Record1/element1'

    teardown()


def test_model_reference():
    """
    Tests if the referenced nodes are properly read from the file.
    """
    autosarfactory.read(input_files)
    port = autosarfactory.get_node('/Swcs/asw1/outPort')
    assert (port is not None), 'port should not be None'
    assert(isinstance(port, autosarfactory.PPortPrototype)), 'port should be an instance of PPortPrototype'

    srIf = port.get_providedInterface()
    assert (srIf is not None), 'srIf should not be None'
    assert(isinstance(srIf, autosarfactory.SenderReceiverInterface)), 'srIf should be an instance of SenderReceiverInterface'
    assert (srIf.path == '/Interfaces/srif1'), 'path should be /Interfaces/srif1'

    vdp = next(iter(srIf.get_dataElements()))
    refType = vdp.get_type()
    assert (refType is not None), 'refType should not be None'
    assert(isinstance(refType, autosarfactory.ImplementationDataType)), 'refType should be an instance of ImplementationDataType'
    assert (refType.name == 'uint8'), 'name should be uint8'
    assert (refType.path == '/DataTypes/ImplTypes/uint8'), 'path should be /DataTypes/ImplTypes/uint8'

    baseType = next(iter(refType.get_swDataDefProps().get_swDataDefPropsVariants())).get_baseType()
    assert (baseType is not None), 'baseType should not be None'
    assert(isinstance(baseType, autosarfactory.SwBaseType)), 'baseType should be an instance of SwBaseType'
    assert (baseType.name == 'uint8'), 'name should be uint8'
    assert (baseType.path == '/DataTypes/baseTypes/uint8'), 'path should be /DataTypes/baseTypes/uint8'
    teardown()

def test_model_read_attributes():
    """
    Tests if the attributes are properly read from the file.
    """
    autosarfactory.read(input_files)
    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    assert (te is not None), 'te should not be None'
    assert(te.get_period() == 0.005), 'value of period should be 0.005'

    vdp = autosarfactory.get_node('/Interfaces/srif1/de1')
    assert (vdp is not None), 'vdp should not be None'
    assert(isinstance(vdp.get_initValue(), autosarfactory.NumericalValueSpecification)), 'init value should be an instance of NumericalValueSpecification'
    assert(vdp.get_initValue().get_value().get() == '1'), 'init value should be 1'

    # check for different types of int values(hex, binary, oct, decimal)
    filter_node = next(iter(autosarfactory.get_node('/Swcs/asw2/inPort').get_requiredComSpecs())).get_filter()
    assert (filter_node is not None), 'filter_node should not be None'
    assert(filter_node.get_mask() == 4095), 'value of mask should be 4095' # hex value in arxml
    assert(filter_node.get_max() == 15), 'value of max should be 15' # binary value in arxml
    assert(filter_node.get_min() == 375), 'value of min should be 375' # oct value in arxml
    teardown()


def test_model_modify():
    """
    Tests if the elements in the model can be modified
    """
    autosarfactory.read(input_files)
    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    assert (te is not None), 'te should not be None'
    assert(te.get_period() == 0.005), 'value of period should be 0.005'
    te.set_period(2000)
    assert(te.get_period() == 2000), 'value of period should be 2000'
    teardown()

def test_model_create_entity():
    """
    Tests if the elements can be created and added to the model
    """
    autosarfactory.read(input_files)
    pack = autosarfactory.get_node('/Interfaces')
    assert (isinstance(pack, autosarfactory.ARPackage)), 'should be instance of ARPackage'

    csif = pack.new_ClientServerInterface('csif')
    op1 = csif.new_Operation('op1')
    arg1 = op1.new_Argument('arg1')
    arg1.set_type(autosarfactory.get_node('/DataTypes/ImplTypes/uint8'))

    assert (len(pack.get_elements()) == 2), '2 elements expected'
    csInterafce = next((x for x in pack.get_elements() if x.name == 'csif'), None)
    assert (csInterafce is not None), 'csInterafce should not be None'
    assert (isinstance(csInterafce, autosarfactory.ClientServerInterface)), 'should be an instance of ClientServerInterface'
    assert(csInterafce.path == '/Interfaces/csif'), 'path should be /Interfaces/csif'

    assert (len(csInterafce.get_operations()) == 1), '1 operation expected'
    operation = next(iter(csInterafce.get_operations()))
    assert (isinstance(operation, autosarfactory.ClientServerOperation)), 'should be an instance of ClientServerOperation'
    assert(operation.name == 'op1'), 'name should be op1'
    assert(operation.path == '/Interfaces/csif/op1'), 'path should be /Interfaces/csif/op1'

    assert (len(operation.get_arguments()) == 1), '1 argument expected'
    argument = next(iter(operation.get_arguments()))
    assert (isinstance(argument, autosarfactory.ArgumentDataPrototype)), 'should be an instance of ArgumentDataPrototype'
    assert(argument.name == 'arg1'), 'name should be arg1'
    assert(isinstance(argument.get_type(), autosarfactory.ImplementationDataType)), 'type should be ImplementationDataType'
    assert(argument.get_type().path == '/DataTypes/ImplTypes/uint8'), 'path of type should be /DataTypes/ImplTypes/uint8'
    teardown()


def test_model_save():
    """
    Tests if the model is saved after making changes.
    """
    autosarfactory.read(input_files)
    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    assert (te is not None), 'te should not be None'
    assert(te.get_period() == 0.005), 'value of period should be 0.005'
    te.set_period(2000)

    #copy the input files to a difference location and compare between the old and new files.
    componentArxml = os.path.join(resourcesDir, 'components.arxml')
    tempDir = _create_temp_dir()
    tempComponentArxml = os.path.join(tempDir, 'components.arxml')
    shutil.copy(componentArxml, tempDir)

    autosarfactory.save()
    assert (filecmp.cmp(componentArxml, tempComponentArxml) is False), "files should be different"

    #copy back the originalfile
    shutil.copy(tempComponentArxml, resourcesDir)
    teardown()

def test_model_save_selected_files():
    """
    Tests if the model is saved after making changes.
    """
    autosarfactory.read(input_files)
    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    assert (te is not None), 'te should not be None'
    assert(te.get_period() == 0.005), 'value of period should be 0.005'
    te.set_period(2000)

    #create new file
    newFile = os.path.join(resourcesDir, 'newFileToSave.arxml')
    arPackage = autosarfactory.new_file(newFile,overWrite=True,defaultArPackage='myPack')
    swc = arPackage.new_ApplicationSwComponentType('swc')
    interface = arPackage.new_SenderReceiverInterface('if')

    port = swc.new_PPortPrototype('port')
    port.set_providedInterface(interface)

    #copy the input files to a difference location and compare between the old and new files.
    componentArxml = os.path.join(resourcesDir, 'components.arxml')
    tempDir = _create_temp_dir()
    tempComponentArxml = os.path.join(tempDir, 'components.arxml')
    shutil.copy(componentArxml, tempDir)

    autosarfactory.save([newFile])
    assert (filecmp.cmp(componentArxml, tempComponentArxml) is True), "files should be same as the save action should not make the component.arxml file"

    os.remove(newFile)
    teardown()

def test_model_saveas():
    """
    Tests if the model is saved to a single file with saveas.
    """
    autosarfactory.read(input_files)
    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    assert (te is not None), 'te should not be None'
    assert(te.get_period() == 0.005), 'value of period should be 0.005'
    te.set_period(2000)

    mergedArxml = os.path.join(resourcesDir, 'merged.arxml')
    autosarfactory.saveAs(mergedArxml,overWrite=True)
    assert (os.path.isfile(mergedArxml)), 'file should be created after saveAs'
    os.remove(mergedArxml)
    teardown()

def test_model_read_saved_file():
    """
    Test if the value saved to the file is read back.
    """
    autosarfactory.read(input_files)
    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    assert (te is not None), 'te should not be None'
    assert(te.get_period() == 0.005), 'value of period should be 0.005'
    te.set_period(2000)

    #copy the input files to a difference location and compare between the old and new files.
    componentArxml = os.path.join(resourcesDir, 'components.arxml')
    tempDir = _create_temp_dir()
    tempComponentArxml = os.path.join(tempDir, 'components.arxml')
    shutil.copy(componentArxml, tempDir)

    autosarfactory.save()
    teardown(deleteTempDir=False)

    autosarfactory.read([componentArxml])
    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    assert (te is not None), 'te should not be None'
    assert(te.get_period() == 2000), 'value of period should be 2000'
    
    #copy back the originalfile
    shutil.copy(tempComponentArxml, resourcesDir)
    teardown()

def test_model_exception_when_create_new_file():
    """
    Test if an exception is raised when the file exists during new file creation
    """
    newFile = os.path.join(resourcesDir, 'newFile.arxml')
    autosarfactory.new_file(newFile, overWrite=True)

    with pytest.raises(FileExistsError) as cm:
        autosarfactory.new_file(newFile)
        assert ('File {} already exists. If it needs overwriting, then please set True for argument overWrite.'.format(newFile) == str(cm.exception)) 
    
    teardown()

def test_model_exception_when_no_short_name_for_referrable_types():
    """
    Test if an exception is raised when short name is not provided for referrable types
    """
    autosarfactory.read(input_files)
    asw1 = autosarfactory.get_node('/Swcs/asw1')

    with pytest.raises(autosarfactory.NoShortNameException) as cm:
        asw1.new_PPortPrototype()
        assert ('name should not be None for Referrable objects' == str(cm.exception)) 
    
    teardown()

def test_model_exception_when_invalid_child_or_ref_added():
    """
    Test if an exception is raised when an invalid child is added to a node.
    Or an invalid reference value is set.
    """
    autosarfactory.read(input_files)
    asw1 = autosarfactory.get_node('/Swcs/asw1')
    asw1.new_PPortPrototype('p1')

    #duplicate child addition
    with pytest.raises(autosarfactory.InvalidRefOrChildNodeException) as cm:
        asw1.new_PPortPrototype('p1')
        assert ('Operation not possible. A node with name {} already present in {}.'.format('p1', asw1) == str(cm.exception)) 
    
    srIf = autosarfactory.SenderReceiverInterface()
    srIf.name = 'srIf'
    
    #invaid child addition
    with pytest.raises(autosarfactory.InvalidRefOrChildNodeException) as cm:
        asw1.add_port(srIf)
        assert ('Operation not possible. {} should be an instance of PortPrototype or its sub-classes'.format(srIf) == str(cm.exception)) 

    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    #invalid refeerence setting
    with pytest.raises(autosarfactory.InvalidRefOrChildNodeException) as cm:
        te.set_startOnEvent(srIf)
        assert ('Operation not possible. {} should be an instance of RunnableEntity or its sub-classes'.format(srIf) == str(cm.exception)) 

    teardown()

def test_model_referenced_by_elements():
    """
    Tests if the model elements return the actual nodes which refer a particular node
    """
    autosarfactory.read(input_files)
    srIf = autosarfactory.get_node('/Interfaces/srif1')
    assert (len(srIf.referenced_by) == 2), 'should be referenced by 2 elements'
    
    for ref_by in srIf.referenced_by:
        if isinstance(ref_by, autosarfactory.PPortPrototype):
            assert (ref_by.name == 'outPort'), 'name should be outPort'
            assert (ref_by.get_providedInterface() == srIf), 'interfaces should be same'
        elif isinstance(ref_by, autosarfactory.RPortPrototype):
            assert (ref_by.name == 'inPort'), 'name should be inPort'
            assert (ref_by.get_requiredInterface() == srIf), 'interfaces should be same'

    swc = autosarfactory.get_node('/Swcs/asw1')
    port = swc.new_PRPortPrototype('p1')
    port.set_providedRequiredInterface(srIf)
    assert (len(srIf.referenced_by) == 3), 'should be referenced by 3 elements'
    
    for ref_by in srIf.referenced_by:
        if isinstance(ref_by, autosarfactory.PPortPrototype):
            assert (ref_by.name == 'outPort'), 'name should be outPort'
            assert (ref_by.get_providedInterface() == srIf), 'interfaces should be same'
        elif isinstance(ref_by, autosarfactory.RPortPrototype):
            assert (ref_by.name == 'inPort'), 'name should be inPort'
            assert (ref_by.get_requiredInterface() == srIf), 'interfaces should be same'
        elif isinstance(ref_by, autosarfactory.PRPortPrototype):
            assert (ref_by ==  port), 'nodes should be same'
            assert (ref_by.name == 'p1'), 'name should be p1'
            assert (ref_by.get_providedRequiredInterface() == srIf), 'interfaces should be same'
    
    csIf = srIf.get_parent().new_ClientServerInterface('csIf')
    port.set_providedRequiredInterface(csIf)

    assert (len(srIf.referenced_by) == 2), 'should be referenced by 2 elements'
    for ref_by in srIf.referenced_by:
        if isinstance(ref_by, autosarfactory.PPortPrototype):
            assert (ref_by.name == 'outPort'), 'name should be outPort'
            assert (ref_by.get_providedInterface() == srIf), 'interfaces should be same'
        elif isinstance(ref_by, autosarfactory.RPortPrototype):
            assert (ref_by.name == 'inPort'), 'name should be inPort'
            assert (ref_by.get_requiredInterface() == srIf), 'interfaces should be same'    

    assert (len(csIf.referenced_by) == 1), 'should be referenced by 1 element'
    ref_by = next(iter(csIf.referenced_by))
    assert (isinstance(ref_by, autosarfactory.PRPortPrototype)), 'should be instance of PRPortPrototype'
    assert (ref_by ==  port), 'nodes should be same'
    assert (ref_by.name == 'p1'), 'name should be p1'
    assert (ref_by.get_providedRequiredInterface() == csIf), 'interfaces should be same'

    mergedArxml = os.path.join(resourcesDir, 'merged.arxml')
    autosarfactory.saveAs(mergedArxml,overWrite=True)
    teardown(deleteTempDir=False)

    # again read the file and check if the values and references exist
    autosarfactory.read([mergedArxml])
    srIf = autosarfactory.get_node('/Interfaces/srif1')
    assert (len(srIf.referenced_by) == 2), 'should be referenced by 2 elements'
    
    for ref_by in srIf.referenced_by:
        if isinstance(ref_by, autosarfactory.PPortPrototype):
            assert (ref_by.name == 'outPort'), 'name should be outPort'
            assert (ref_by.get_providedInterface() == srIf), 'interfaces should be same'
        elif isinstance(ref_by, autosarfactory.RPortPrototype):
            assert (ref_by.name == 'inPort'), 'name should be inPort'
            assert (ref_by.get_requiredInterface() == srIf), 'interfaces should be same'

    csIf = autosarfactory.get_node('/Interfaces/csIf')
    assert (len(csIf.referenced_by) == 1), 'should be referenced by 1 element'
    ref_by = next(iter(csIf.referenced_by))
    assert (isinstance(ref_by, autosarfactory.PRPortPrototype)), 'should be instance of PRPortPrototype'
    assert (ref_by.name == 'p1'), 'name should be p1'
    assert (ref_by.get_providedRequiredInterface() == csIf), 'interfaces should be same'
    teardown()


def test_model_get_all_instances():
    """
    Tests if the model returns the right instances when the method get_all_instances is called
    """
    root, status = autosarfactory.read(input_files)
    runnables = autosarfactory.get_all_instances(root, autosarfactory.RunnableEntity)
    assert (len(runnables) == 2), '2 runnables in the whole model'

    runnables = autosarfactory.get_all_instances(autosarfactory.get_node('/Swcs/asw1'), autosarfactory.RunnableEntity)
    assert (len(runnables) == 1), '1 runnable in the swc asw1'
    teardown()


def test_xml_order_elements():
    """
    Tests if the elements were added in the right sequence as specified by Autosar
    """
    autosarfactory.read(input_files)
    runnable = autosarfactory.get_all_instances(autosarfactory.get_node('/Swcs/asw1'), autosarfactory.RunnableEntity)[0]

    # Runnable just contains the elements DataSendPoints and Symbol initially 

    # attribute CanBeInvokedConcurrently must be added after ShortName and before DataSendPoints
    runnable.set_canBeInvokedConcurrently(True)

    # Data write access should be added after DataSendPoint and before Symbol
    dwa = runnable.new_DataWriteAcces('dwa1')
    var = dwa.new_AccessedVariable().new_AutosarVariable()
    var.set_portPrototype(autosarfactory.get_node('/Swcs/asw1/outPort'))
    var.set_targetDataPrototype(autosarfactory.get_node('/Interfaces/srif1/de1'))

    # Short name must be added as the first element
    runnable.set_shortName("run1")

    autosarfactory.save()

    # Read saved xml manually and see if the order of the elements are as expected by schema.
    tree = etree.parse(os.path.join(resourcesDir, 'components.arxml'), etree.XMLParser(remove_blank_text=True))
    runnables = tree.findall(".//{*}RUNNABLE-ENTITY")
    for run in runnables:
        if run.find('{*}SHORT-NAME').text == 'run1':
            assert (run[0].tag == '{http://autosar.org/schema/r4.0}SHORT-NAME'), 'First child must be SHORT-NAME'
            assert (run[1].tag == '{http://autosar.org/schema/r4.0}CAN-BE-INVOKED-CONCURRENTLY'), 'Second child must be CAN-BE-INVOKED-CONCURRENTLY'
            assert (run[2].tag == '{http://autosar.org/schema/r4.0}DATA-SEND-POINTS'), 'Third child must be DATA-SEND-POINTS'
            assert (run[3].tag == '{http://autosar.org/schema/r4.0}DATA-WRITE-ACCESSS'), 'Fourth child must be DATA-WRITE-ACCESSS'
            assert (run[4].tag == '{http://autosar.org/schema/r4.0}SYMBOL'), 'Last child must be SYMBOL'
            break
    teardown()

def test_xml_order_elements_with_invisible_model_element():
    """
    Tests if the elements were added in the right sequence as specified by Autosar when the model elements doesn't appear in arxml
    """
    autosarfactory.read(input_files)
    uint8BaseType = autosarfactory.get_node('/DataTypes/baseTypes/uint8')

    # uint8 base type just contains the child elements shortName and MemAlignment

    baseTypeDef = uint8BaseType.new_BaseTypeDirectDefinition() # create the invisible model element BaseTypeDirectDefinition

    # BaseTypeEncoding should be added after ShortName and before MemAlignment
    baseTypeDef.set_baseTypeEncoding('2C')

    # NativeDeclaration should be added after MemAlignment
    baseTypeDef.set_nativeDeclaration('unsigned char')

    # BaseTypeSize should be added after ShortName and before BaseTypeEncoding and MemAlignment
    baseTypeDef.set_baseTypeSize(8)

    autosarfactory.save()

    # Read saved xml manually and see if the order of the elements are as expected by schema.
    tree = etree.parse(os.path.join(resourcesDir, 'datatypes.arxml'), etree.XMLParser(remove_blank_text=True))
    baseTypeFromFile = tree.findall(".//{*}SW-BASE-TYPE")[0]

    assert (baseTypeFromFile[0].tag == '{http://autosar.org/schema/r4.0}SHORT-NAME'), 'First child must be SHORT-NAME'
    assert (baseTypeFromFile[1].tag == '{http://autosar.org/schema/r4.0}BASE-TYPE-SIZE'), 'Second child must be BASE-TYPE-SIZE'
    assert (baseTypeFromFile[1].text == '8'), 'Value must be 8'
    assert (baseTypeFromFile[2].tag == '{http://autosar.org/schema/r4.0}BASE-TYPE-ENCODING'), 'Third child must be BASE-TYPE-ENCODING'
    assert (baseTypeFromFile[2].text == '2C'), 'Value must be 2C'
    assert (baseTypeFromFile[3].tag == '{http://autosar.org/schema/r4.0}MEM-ALIGNMENT'), 'Fourth child must be MEM-ALIGNMENT'
    assert (baseTypeFromFile[4].tag == '{http://autosar.org/schema/r4.0}NATIVE-DECLARATION'), 'Last child must be NATIVE-DECLARATION'
    assert (baseTypeFromFile[4].text == 'unsigned char'), 'Value must be unsigned char'

    teardown()

def test_xml_element_removed_when_value_is_unset():
    """
    Tests if the xml elements are removed when the value for the attribute or reference is unset or set to None.
    """
    autosarfactory.read(input_files)
    
    runnable = autosarfactory.get_all_instances(autosarfactory.get_node('/Swcs/asw1'), autosarfactory.RunnableEntity)[0]
    # Runnable contains the Symbol and we are trying to unset it.
    assert (runnable.get_symbol() is not None), 'symbol should not be None'
    runnable.set_symbol(None)
    
    dre = autosarfactory.get_all_instances(autosarfactory.get_node('/Swcs/asw2'), autosarfactory.DataReceivedEvent)[0]
    # Timing Event has a reference to runnable. We are trying to unset it.
    assert (dre.get_startOnEvent() is not None), 'runnable reference should not be None'
    dre.set_startOnEvent(None)

    autosarfactory.save()

    # Read saved xml manually and see if the symbol attribute and runnable reference are removed
    tree = etree.parse(os.path.join(resourcesDir, 'components.arxml'), etree.XMLParser(remove_blank_text=True))
    runnableFromXmlfile = tree.findall(".//{*}RUNNABLE-ENTITY")[0]
    assert(runnableFromXmlfile.find('{*}SYMBOL') is None), 'SYMBOL element should not exist'

    dreFromXmlfile = tree.findall(".//{*}DATA-RECEIVED-EVENT")[0]
    assert(dreFromXmlfile.find('{*}START-ON-EVENT-REF') is None), 'START-ON-EVENT-REF element should not exist'

    teardown()

def test_read_choice_elements():
    """
    Tests if the autosarfactory was able to read choice elements properly from the input model. For eg: SD element inside SDG
    """
    autosarfactory.read(input_files)
    port = autosarfactory.get_node('/Swcs/asw1/outPort')

    # Read SpecialDataGroups
    sdgs = port.get_adminData().get_sdgs()
    assert (len(sdgs) == 2), '2 SDG'
    sdg = next(iter(sdgs))
    assert (sdg.get_gid() == 'my_id'), 'GID should be my_id'
    assert (next(iter(sdg.get_sds())).get_value() == 'version-1234'), 'SD value should be version-1234'

    teardown()

def test_model_remove_element():
    """
    Tests if the elements are removed from the model
    """
    autosarfactory.read(input_files)

    # check removal of containment elements
    package = autosarfactory.get_node('/Swcs')
    swc = autosarfactory.get_node('/Swcs/asw1')
    package.remove_element(swc)

    # check removal of referenced elements
    swcEcuMapping = autosarfactory.get_node('/Swcs/CanSystem/Mappings/SwcMapping')
    swcProto = autosarfactory.get_node('/Swcs/Comp/asw1_proto')
    assert (isinstance(swcEcuMapping, autosarfactory.SwcToEcuMapping)), 'should be instance of SwcToEcuMapping'
    assert (len(swcEcuMapping.get_components()) == 1), 'should be one instance of component'
    assert (isinstance(swcProto, autosarfactory.SwComponentPrototype)), 'should be instance of SwComponentPrototype'
    swcEcuMapping.get_components()[0].remove_contextComponent(swcProto)
    assert (len(swcEcuMapping.get_components()[0].get_contextComponents()) == 1), 'only 1 component exists after removing the asw1'
    assert (swcEcuMapping.get_components()[0].get_contextComponents()[0].name == 'asw2_proto'), 'name should be asw2_proto'

    autosarfactory.save()
    teardown(deleteTempDir=False)

    # Read saved xml manually and see if the element is removed
    tree = etree.parse(os.path.join(resourcesDir, 'components.arxml'), etree.XMLParser(remove_blank_text=True))
    swcFromXmlFile = tree.findall(".//{*}APPLICATION-SW-COMPONENT-TYPE")
    for swc in swcFromXmlFile:
        assert(swc.find('{*}SHORT-NAME').text != 'asw1'), 'swc with name asw1 must not exist as its removed'

    contextComponentRefs = tree.findall(".//{*}COMPONENT-IREF")[0].findall(".//{*}CONTEXT-COMPONENT-REF")
    assert (len(contextComponentRefs) == 1), 'should be one instance of CONTEXT-COMPONENT-REF'
    assert (contextComponentRefs[0].text == '/Swcs/Comp/asw2_proto'), 'context ref should have reference to asw2_proto'

    # Re-read the file and removal all elements under the arpackage and see if the file is updated properly.
    autosarfactory.read(input_files)
    package = autosarfactory.get_node('/Swcs')
    swc = autosarfactory.get_node('/Swcs/asw2')
    compo = autosarfactory.get_node('/Swcs/Comp')
    system = autosarfactory.get_node('/Swcs/CanSystem')
    package.remove_element(swc)
    package.remove_element(compo)
    package.remove_element(system)
    assert(len(package.get_elements()) == 0), 'no elements expected'

    autosarfactory.save()
    # Read saved xml manually and see if the elements are removed
    tree = etree.parse(os.path.join(resourcesDir, 'components.arxml'), etree.XMLParser(remove_blank_text=True))
    arpackages = tree.findall(".//{*}AR-PACKAGE")
    for pack in arpackages:
        if pack.find('{*}SHORT-NAME').text == 'Swcs':
            assert(len(pack.findall(".//{*}APPLICATION-SW-COMPONENT-TYPE")) == 1), 'only one swc expected in the arpackage path /Swcs/Swcs_hierarchy1/Swcs_hierarchy2/asw123. Ones inside Swcs package are removed'
            assert(len(pack.findall(".//{*}COMPOSITION-SW-COMPONENT-TYPE")) == 0), 'no composition expected as its already removed'
            assert(len(pack.findall(".//{*}SYSTEM")) == 0), 'no system expected as its already removed'
            break
    
    teardown()

def test_model_export():
    """
    Tests if an element is exported to a file
    """
    autosarfactory.read(input_files)

    # 1. export function per node
    swc = autosarfactory.get_node('/Swcs/Swcs_hierarchy1/Swcs_hierarchy2/asw123')
    swc.export_to_file(os.path.join(resourcesDir, 'asw123Export.arxml'), overWrite = True)

    # 2. generic export function on the autosarfactory
    implPack = autosarfactory.get_node('/DataTypes/ImplTypes')
    autosarfactory.export_to_file(implPack, os.path.join(resourcesDir, 'ImplTypesExport.arxml'), overWrite = True)

    # exception if un-intended element is called for export.
    port = autosarfactory.get_node('/Swcs/asw1/outPort')
    with pytest.raises(Exception) as cm:
        autosarfactory.export_to_file(port, os.path.join(resourcesDir, 'portExport.arxml'), overWrite = True)
        assert ('Only elements of type CollectableElement can be exported(for eg: ARPackage, ApplicationSwComponentType, ISignal etc etc.)' == str(cm.exception)) 

    # Read the exported file in 1 and 2 and see if the contents exist
    # 1
    tree = etree.parse(os.path.join(resourcesDir, 'asw123Export.arxml'), etree.XMLParser(remove_blank_text=True))
    swcFromXmlFile = tree.findall(".//{*}APPLICATION-SW-COMPONENT-TYPE")
    assert(len(swcFromXmlFile) == 1), 'only one swc exists'
    assert(swcFromXmlFile[0].find('{*}SHORT-NAME').text == 'asw123'), 'name of swc must be asw123'

    #2
    tree = etree.parse(os.path.join(resourcesDir, 'ImplTypesExport.arxml'), etree.XMLParser(remove_blank_text=True))
    ImplFromXmlFile = tree.findall(".//{*}IMPLEMENTATION-DATA-TYPE")
    assert(len(ImplFromXmlFile) == 1), 'only one IDT exists'
    assert(ImplFromXmlFile[0].find('{*}SHORT-NAME').text == 'uint8'), 'name of IDT must be uint8'

    teardown()

def test_model_path_reference_with_parent_having_no_short_name():
    """
    Tests if the reference path is properly set if the element has a parent with no short name.
    """
    autosarfactory.read(input_files)

    # Referencing an element whose parent node doesn't have a short-name
    map1 = autosarfactory.get_node('/RootPackage/map1')
    map2 = map1.get_parent().new_DiagnosticServiceSwMapping('map2')
    # here the recordElement do not have a short-name
    dataElement2 = map1.get_parent().new_DiagnosticExtendedDataRecord('record2').new_RecordElement().new_DataElement('element2')
    map2.set_diagnosticDataElement(dataElement2)
    
    autosarfactory.save()
    # Read saved xml manually and see if the element is removed
    tree = etree.parse(os.path.join(resourcesDir, 'diag_sw_mapping.arxml'), etree.XMLParser(remove_blank_text=True))
    diagSwMappings = tree.findall(".//{*}DIAGNOSTIC-SERVICE-SW-MAPPING")
    for diag in diagSwMappings:
        if (diag.find('{*}SHORT-NAME').text == 'map2'):
            assert(diag.find('{*}DIAGNOSTIC-DATA-ELEMENT-REF').text == '/RootPackage/record2/element2'), 'reference path must be /RootPackage/record2/element2'
            break
    
    # Re-read the saved model and see if the reference node is read properly.
    autosarfactory.read(input_files)
    map1 = autosarfactory.get_node('/RootPackage/map2')
    diagDE = map1.get_diagnosticDataElement()
    assert (diagDE is not None), 'diagDE should not be None'
    assert (diagDE.autosar_path == '/RootPackage/record2/element2'), 'diagDE path must be /RootPackage/record2/element2'

    teardown()

def test_model_retrieval_of_elements_with_one_concrete_sub_type():
    """
    Tests if the model is able to properly retrieve elements which has only one sub-type in the autosar metamodel.
    """
    autosarfactory.read(input_files)
    machineDesign = autosarfactory.get_node('/RootPackage/MachineDesign')
    
    # The element SERVICE-DISCOVERY-CONFIG can have only one type of sub concrete type 'SomeipServiceDiscovery' although it has a base class ServiceDiscoveryConfiguration.
    configs = machineDesign.get_serviceDiscoveryConfigs()
    assert (len(configs) == 1), 'only one config is expected'
    assert (configs[0].get_someipServiceDiscoveryPort() == 1234), 'discovery port must be 1234'
    teardown()

def test_model_get_ref_proxy_node():
    """
    Tests if the model is able return the reference value as path. This will be useful if the referenced node itself is missing.
    """
    autosarfactory.read([os.path.join(resourcesDir, 'interfaces.arxml')])
    de = autosarfactory.get_node('/Interfaces/srif1/de1')
    assert (isinstance(de.get_type(), autosarfactory.UnresolvedRef))
    assert (de.get_type().is_proxy())
    assert (de.get_type().path == '/DataTypes/ImplTypes/uint8')
    teardown()

def test_model_set_ref_value_with_no_referable_parent():
    """
    Tests if the model is able set the reference value to an element when the reference value has an element which do not have a short-name(and hence not referable).
    """
    pack = autosarfactory.new_file(path=os.path.join(resourcesDir, 'tempTest_set_Ref.arxml'), defaultArPackage='TestPackage', overWrite = True)
    # CanClusterVariant is not referable and is not supposed to accept short-name. 
    # The tooling internally must ignore if short-name is provided(both at element level and where it's sub-elements are referenced too)
    canChannel = pack.new_CanCluster('Can_Cluster_0').new_CanClusterVariant('variant').new_CanPhysicalChannel('Can_channel_0')
    sigTrig = canChannel.new_ISignalTriggering('sigTrig')
    pduTrig = canChannel.new_PduTriggering('pduTrig')
    pduTrig.new_ISignalTriggering().set_iSignalTriggering(sigTrig)
    autosarfactory.save()

    autosarfactory.read([os.path.join(resourcesDir, 'tempTest_set_Ref.arxml')])
    pduTrigFromFile = autosarfactory.get_node('/TestPackage/Can_Cluster_0/Can_channel_0/pduTrig')
    assert (pduTrigFromFile is not None)
    assert (pduTrigFromFile.get_iSignalTriggerings()[0] is not None)
    assert (pduTrigFromFile.get_iSignalTriggerings()[0].get_iSignalTriggering() is not None)
    assert (pduTrigFromFile.get_iSignalTriggerings()[0].get_iSignalTriggering().autosar_path == '/TestPackage/Can_Cluster_0/Can_channel_0/sigTrig')
    teardown()

def test_read_compu_method():
    """
    Tests if the compu methods are read properly.
    """
    autosarfactory.read([os.path.join(resourcesDir, 'datatypes.arxml')])
    cms = autosarfactory.get_all_instances(autosarfactory.get_root(), autosarfactory.CompuMethod)

    closedIntervalCm :autosarfactory.CompuMethod = cms[0]
    formulaCm :autosarfactory.CompuMethod = cms[1]

    assert (isinstance(closedIntervalCm.get_compuInternalToPhys().get_compuContent(), autosarfactory.CompuScales))
    cmScales :autosarfactory.CompuScales = closedIntervalCm.get_compuInternalToPhys().get_compuContent()

    ecu_stop = cmScales.get_compuScales()[0]
    assert(ecu_stop.get_lowerLimit().get() == '0')
    assert(ecu_stop.get_upperLimit().get() == '0')

    assert(isinstance(ecu_stop.get_compuScaleContents(), autosarfactory.CompuScaleConstantContents))
    cmConst :autosarfactory.CompuScaleConstantContents = ecu_stop.get_compuScaleContents()
    assert(isinstance(cmConst.get_compuConst().get_compuConstContentType(), autosarfactory.CompuConstTextContent))
    cmContent :autosarfactory.CompuConstTextContent = cmConst.get_compuConst().get_compuConstContentType()
    assert(cmContent.get_vt() == 'ECU_STATE_STOP')

    assert (isinstance(formulaCm.get_compuInternalToPhys().get_compuContent(), autosarfactory.CompuScales))
    cmScales :autosarfactory.CompuScales = formulaCm.get_compuInternalToPhys().get_compuContent()

    cmScale = cmScales.get_compuScales()[0]
    assert(isinstance(cmScale.get_compuScaleContents(), autosarfactory.CompuScaleRationalFormula))
    formula :autosarfactory.CompuScaleRationalFormula = cmScale.get_compuScaleContents()

    vs = formula.get_compuRationalCoeffs().get_compuNumerator().get_vs()
    assert(vs[0].get() == '100')
    assert(vs[1].get() == '200')
    assert(vs[2].get() == '300')

    teardown()

def test_read_split_files():
    """
    Tests if the contents in split files are read properly.
    """
    autosarfactory.read([os.path.join(resourcesDir, 'split1.arxml'),os.path.join(resourcesDir, 'split2.arxml')])
    components = autosarfactory.get_node('/System/Composition_A').get_components()

    assert(len(components) == 2)
    assert(components[0].get_type().name == 'Component1')
    assert(components[1].get_type().name == 'Component2')
    teardown()

def test_model_save_with_element_splitted():
    """
    Tests if the model is saved after making changes where elements are splitted across multiple files.
    """
    splitFiles = [os.path.join(resourcesDir, 'split1.arxml'),os.path.join(resourcesDir, 'split2.arxml')]
    autosarfactory.read(splitFiles)
    comp1:autosarfactory.ApplicationSwComponentType = autosarfactory.get_node('/ComponentPkg/Component1')

    #copy the split files to a difference location and compare between the old and new files.
    tempDir = _create_temp_dir()
    for f in splitFiles:
        shutil.copy(f, tempDir)

    #Add a port and save the file
    comp1.new_PPortPrototype('port1')
    autosarfactory.save()

    assert (filecmp.cmp(os.path.join(resourcesDir, 'split1.arxml'), os.path.join(tempDir, 'split1.arxml')) is False), "files should be same as the save action should modify the split1.arxml file"
    assert (filecmp.cmp(os.path.join(resourcesDir, 'split2.arxml'), os.path.join(tempDir, 'split2.arxml')) is True), "files should be same as the save action should not modify the split2.arxml file"

    teardown(deleteTempDir=False)
    #read the file split1.arxml and see if the new port is added
    autosarfactory.read(splitFiles)
    comp1:autosarfactory.ApplicationSwComponentType = autosarfactory.get_node('/ComponentPkg/Component1')
    assert(len(comp1.get_ports()) == 1), '1 port should exists'
    assert(comp1.get_ports()[0].name == 'port1'), 'name of port must be port1'

    #As the split1 file is only loaded, it must only contain one component prototype and component1
    compo:autosarfactory.CompositionSwComponentType = autosarfactory.get_node('/System/Composition_A')
    assert(compo is not None), 'Composition_A must exist'
    assert(len(compo.get_components()) == 2)
    assert(compo.get_components()[0].get_type().name == 'Component1')
    assert(compo.get_components()[1].get_type().name == 'Component2')
    
    # copying back the files to resoursec directory and remove the temp directory
    shutil.copy(os.path.join(tempDir, 'split1.arxml'), resourcesDir)
    shutil.copy(os.path.join(tempDir, 'split2.arxml'), resourcesDir)

    teardown()

def test_model_save_selected_files_with_element_splitted():
    """
    Tests if the model is saved after making changes where elements are splitted across multiple files.
    """
    splitFiles = [os.path.join(resourcesDir, 'split1.arxml'),os.path.join(resourcesDir, 'split2.arxml')]
    autosarfactory.read(splitFiles)
    comp1:autosarfactory.ApplicationSwComponentType = autosarfactory.get_node('/ComponentPkg/Component1')

    #copy the split files to a difference location and compare between the old and new files.
    tempDir = _create_temp_dir()
    for f in splitFiles:
        shutil.copy(f, tempDir)

    #Add a port and save the file
    comp1.new_PPortPrototype('port1')
    autosarfactory.save([os.path.join(resourcesDir, 'split1.arxml')])

    assert (filecmp.cmp(os.path.join(resourcesDir, 'split1.arxml'), os.path.join(tempDir, 'split1.arxml')) is False), "files should be same as the save action should modify the split1.arxml file"
    assert (filecmp.cmp(os.path.join(resourcesDir, 'split2.arxml'), os.path.join(tempDir, 'split2.arxml')) is True), "files should be same as the save action should not modify the split2.arxml file"

    teardown(deleteTempDir=False)
    #read the file split1.arxml and see if the new port is added
    autosarfactory.read([os.path.join(resourcesDir, 'split1.arxml')])
    comp1:autosarfactory.ApplicationSwComponentType = autosarfactory.get_node('/ComponentPkg/Component1')
    assert(len(comp1.get_ports()) == 1), '1 port should exists'
    assert(comp1.get_ports()[0].name == 'port1'), 'name of port must be port1'

    #As the split1 file is only loaded, it must only contain one component prototype and component1
    compo:autosarfactory.CompositionSwComponentType = autosarfactory.get_node('/System/Composition_A')
    assert(compo is not None), 'Composition_A must exist'
    assert(len(compo.get_components()) == 1)
    assert(compo.get_components()[0].get_type().name == 'Component1')
    
    assert(len(comp1.get_parent().get_elements()) == 1), 'only 1 child element of ComponentPkg'
    assert(comp1.get_parent().get_elements()[0].name == 'Component1'), 'only component1 shall exists'


    # copying back the files to resoursec directory and remove the temp directory
    shutil.copy(os.path.join(tempDir, 'split1.arxml'), resourcesDir)
    shutil.copy(os.path.join(tempDir, 'split2.arxml'), resourcesDir)

    teardown()

def test_model_fragments_across_multiple_files():
    """
    Tests the contributing_files/get_fragment_files/get_fragment APIs for
    atp-splitable nodes whose content is merged in from multiple files.
    """
    splitFiles = [os.path.join(resourcesDir, 'split1.arxml'), os.path.join(resourcesDir, 'split2.arxml')]
    autosarfactory.read(splitFiles)
    file1, file2 = splitFiles[0], splitFiles[1]

    # Composition_A is defined in both files (each contributes one component), so it is merged.
    compo:autosarfactory.CompositionSwComponentType = autosarfactory.get_node('/System/Composition_A')
    assert (compo is not None), 'Composition_A must exist'
    assert (compo.contributing_files == {file1, file2}), 'Composition_A content should come from both split files'
    assert (sorted(compo.get_fragment_files()) == sorted([file1, file2])), 'get_fragment_files should list both files'    
    assert (compo.get_fragment(compo.file) is compo), 'fragment for its own file should be the node itself'

    # the other file's fragment is a distinct object parsed from that file
    other_file = file2 if compo.file == file1 else file1
    fragment = compo.get_fragment(other_file)
    assert (fragment is not None), 'fragment for the other contributing file should exist'
    assert (fragment is not compo), 'fragment object should be distinct from the merged node'
    assert (fragment.file == other_file), 'fragment.file should match the requested file'

    components = compo.get_components()
    assert (len(components) == 2), 'both components must be present after merge'    

    # ComponentPkg itself is also split (each file contributes a different element)
    componentPkg = autosarfactory.get_node('/ComponentPkg')
    assert (componentPkg is not None), 'ComponentPkg must exist'
    assert (componentPkg.contributing_files == {file1, file2}), 'ComponentPkg content should come from both split files'

    # a node that only exists in one file should report just that file, and have no other fragment
    comp1:autosarfactory.ApplicationSwComponentType = autosarfactory.get_node('/ComponentPkg/Component1')
    assert (comp1.contributing_files == {comp1.file}), 'Component1 only exists in its own file'
    assert (comp1.get_fragment(comp1.file) is comp1), 'fragment for its own file should be itself'
    assert (comp1.get_fragment(file2 if comp1.file == file1 else file1) is None), 'no fragment should exist for the other file'

    teardown()

def test_model_add_remove_elements_using_fragment_apis():
    """
    Tests that elements added/removed via get_fragment() ends up in the correct
    physical file.
    """
    splitFiles = [os.path.join(resourcesDir, 'split1.arxml'), os.path.join(resourcesDir, 'split2.arxml')]
    file1, file2 = splitFiles[0], splitFiles[1]

    # copy the split files to a different location so we can restore them afterwards
    tempDir = _create_temp_dir()
    for f in splitFiles:
        shutil.copy(f, tempDir)

    autosarfactory.read(splitFiles)
    compo:autosarfactory.CompositionSwComponentType = autosarfactory.get_node('/System/Composition_A')
    frag1 = compo.get_fragment(file1)
    frag2 = compo.get_fragment(file2)

    # Add a new component into file2's fragment specifically (not the merged node)
    newComp = frag2.new_Component('CPT_Component3')
    newComp.set_type(autosarfactory.get_node('/ComponentPkg/Component2'))

    # Remove the pre-existing component that belongs to file1's fragment.
    comp1 = [c for c in frag1.get_components() if c.name == 'CPT_Component1'][0]
    frag1.remove_component(comp1)

    assert (newComp.file == file2), 'new component created via frag2 should belong to file2'
    assert (newComp.get_parent() is frag2), 'new component should be parented under frag2'
    assert (sorted(c.name for c in frag2.get_components()) == ['CPT_Component2', 'CPT_Component3']), 'frag2 should immediately reflect the newly added component'
    assert (sorted(c.name for c in compo.get_components()) == ['CPT_Component2', 'CPT_Component3']), 'merged node reflects the removal of CPT_Component1 and also addition of CPT_Component3'

    autosarfactory.save()

    # Read saved xml manually and see if the elements are added/removed
    tree1 = etree.parse(file1, etree.XMLParser(remove_blank_text=True))
    tree2 = etree.parse(file2, etree.XMLParser(remove_blank_text=True))
    names1 = [sp.find('{*}SHORT-NAME').text for sp in tree1.findall(".//{*}SW-COMPONENT-PROTOTYPE")]
    names2 = [sp.find('{*}SHORT-NAME').text for sp in tree2.findall(".//{*}SW-COMPONENT-PROTOTYPE")]
    assert (names1 == []), 'split1.arxml must no longer contain any SW-COMPONENT-PROTOTYPE after removing CPT_Component1'
    assert (names2 == ['CPT_Component2', 'CPT_Component3']), 'split2.arxml must contain the original CPT_Component2 plus the newly added CPT_Component3'

    typeRefs2 = [sp.find('{*}TYPE-TREF').text for sp in tree2.findall(".//{*}SW-COMPONENT-PROTOTYPE")]
    assert ('/ComponentPkg/Component2' in typeRefs2), 'new component must reference Component2 on disk'

    teardown(deleteTempDir=False)

    # Read the saved files again and confirm the model reflects the change
    autosarfactory.read(splitFiles)
    compo = autosarfactory.get_node('/System/Composition_A')
    reReadNames = sorted(c.name for c in compo.get_components())
    assert (reReadNames == ['CPT_Component2', 'CPT_Component3']), 're-read model must reflect the add/remove done via fragment apis'
    newCompReRead = [c for c in compo.get_components() if c.name == 'CPT_Component3'][0]
    assert (newCompReRead.file == file2), 're-read CPT_Component3 must belong to split2.arxml'
    assert (newCompReRead.get_type().name == 'Component2'), 're-read CPT_Component3 must reference Component2'

    # restore the original split files and clean up the temp copies
    shutil.copy(os.path.join(tempDir, 'split1.arxml'), resourcesDir)
    shutil.copy(os.path.join(tempDir, 'split2.arxml'), resourcesDir)

    teardown()

def test_model_fragments_merge_keeps_same_typed_slots_separate():
    """
    Tests that merging split files does not mix up containment slots which hold the same python class type.
    """
    file1, file2 = AutosarModelTestHelper.write_split_implementation_files(_create_temp_dir())
    autosarfactory.read([file1, file2])

    impl = autosarfactory.get_node('/P/Impl')
    assert (impl.is_atp_splitable()), 'Impl must be splitable'
    assert (impl.contributing_files == {file1, file2}), 'Impl content should come from both files'
    assert (AutosarModelTestHelper.names(impl.get_generatedArtifacts()) == ['Gen1']), 'only Gen1 belongs to generatedArtifacts'
    assert (AutosarModelTestHelper.names(impl.get_requiredArtifacts()) == ['Req2']), 'only Req2 belongs to requiredArtifacts'
    assert (impl.get_requiredGeneratorTools() == []), 'requiredGeneratorTools must be empty'

    teardown()

def test_model_fragments_add_syncs_to_correct_slot_of_merged_node():
    """
    Tests that an element added through a fragment is mirrored into the same slot of the merged node.
    """
    file1, file2 = AutosarModelTestHelper.write_split_implementation_files(_create_temp_dir())
    autosarfactory.read([file1, file2])

    impl = autosarfactory.get_node('/P/Impl')
    frag2 = impl.get_fragment(file2)
    tool = frag2.new_RequiredGeneratorTool('Tool2')

    assert (tool.file == file2), 'the new element belongs to the fragment it was created in'
    assert (AutosarModelTestHelper.names(impl.get_requiredGeneratorTools()) == ['Tool2']), 'Tool2 must be in requiredGeneratorTools of the merged node'
    assert (AutosarModelTestHelper.names(impl.get_generatedArtifacts()) == ['Gen1']), 'generatedArtifacts must be unaffected'
    assert (AutosarModelTestHelper.names(impl.get_requiredArtifacts()) == ['Req2']), 'requiredArtifacts must be unaffected'

    # adding at an index goes through a different api, it must be synced as well
    artifact = autosarfactory.DependencyOnArtifact()
    artifact.set_shortName('Req3')
    frag2.add_requiredArtifact_at_index(0, artifact)
    assert (AutosarModelTestHelper.names(impl.get_requiredArtifacts()) == ['Req2', 'Req3']), 'Req3 added at an index must be in requiredArtifacts of the merged node'
    assert (AutosarModelTestHelper.names(impl.get_generatedArtifacts()) == ['Gen1']), 'generatedArtifacts must still be unaffected'

    teardown()

def test_model_fragments_remove_syncs_to_correct_slot():
    """
    Tests that removing an element is mirrored in both directions (fragment -> merged node and merged node -> fragment)
    and only affects the slot it was removed from.
    """
    file1, file2 = AutosarModelTestHelper.write_split_implementation_files(_create_temp_dir())
    autosarfactory.read([file1, file2])

    impl = autosarfactory.get_node('/P/Impl')
    frag2 = impl.get_fragment(file2)

    # Before any change, the files hold what they were written with
    assert (AutosarModelTestHelper.slot_contents(file1) == {'GENERATED-ARTIFACTS': ['Gen1'], 'REQUIRED-ARTIFACTS': [], 'REQUIRED-GENERATOR-TOOLS': []}), 'file1 initially holds Gen1'
    assert (AutosarModelTestHelper.slot_contents(file2) == {'GENERATED-ARTIFACTS': [], 'REQUIRED-ARTIFACTS': ['Req2'], 'REQUIRED-GENERATOR-TOOLS': []}), 'file2 initially holds Req2'

    frag2.remove_requiredArtifact(frag2.get_requiredArtifacts()[0])
    assert (frag2.get_requiredArtifacts() == []), 'Req2 must be removed from the fragment'
    assert (impl.get_requiredArtifacts() == []), 'Req2 must be removed from the merged node as well'
    assert (AutosarModelTestHelper.names(impl.get_generatedArtifacts()) == ['Gen1']), 'generatedArtifacts must be unaffected'

    autosarfactory.save()

    # Read saved xml manually and see if Req2 is removed from file2 only
    assert (AutosarModelTestHelper.slot_contents(file1) == {'GENERATED-ARTIFACTS': ['Gen1'], 'REQUIRED-ARTIFACTS': [], 'REQUIRED-GENERATOR-TOOLS': []}), 'file1 must be unchanged'
    assert (AutosarModelTestHelper.slot_contents(file2) == {'GENERATED-ARTIFACTS': [], 'REQUIRED-ARTIFACTS': [], 'REQUIRED-GENERATOR-TOOLS': []}), 'Req2 must be removed from file2'

    # Tool2 belongs to file2, but is removed through the merged node
    tool = frag2.new_RequiredGeneratorTool('Tool2')
    autosarfactory.save()
    assert (AutosarModelTestHelper.slot_contents(file1)['REQUIRED-GENERATOR-TOOLS'] == []), 'Tool2 must not be saved to file2'
    assert (AutosarModelTestHelper.slot_contents(file2)['REQUIRED-GENERATOR-TOOLS'] == ['Tool2']), 'Tool2 must be saved to file2'

    impl.remove_requiredGeneratorTool(tool)
    assert (impl.get_requiredGeneratorTools() == []), 'Tool2 must be removed from the merged node'
    assert (frag2.get_requiredGeneratorTools() == []), 'Tool2 must be removed from the fragment it belongs to'

    autosarfactory.save()

    # Read saved xml manually and see if Tool2 is removed from file2, even though it was removed through the merged node
    assert (AutosarModelTestHelper.slot_contents(file1) == {'GENERATED-ARTIFACTS': ['Gen1'], 'REQUIRED-ARTIFACTS': [], 'REQUIRED-GENERATOR-TOOLS': []}), 'file1 must still be unchanged'
    assert (AutosarModelTestHelper.slot_contents(file2) == {'GENERATED-ARTIFACTS': [], 'REQUIRED-ARTIFACTS': [], 'REQUIRED-GENERATOR-TOOLS': []}), 'Tool2 must be removed from file2'

    teardown()

def test_model_fragments_slots_saved_to_correct_file():
    """
    Tests that same typed slots are saved to the right file and are read back into the right slot.
    """
    file1, file2 = AutosarModelTestHelper.write_split_implementation_files(_create_temp_dir())
    autosarfactory.read([file1, file2])

    impl = autosarfactory.get_node('/P/Impl')
    impl.get_fragment(file2).new_RequiredGeneratorTool('Tool2')
    autosarfactory.save()

    # Read saved xml manually and check which file holds which slot
    assert (AutosarModelTestHelper.slot_contents(file1) == {'GENERATED-ARTIFACTS': ['Gen1'], 'REQUIRED-ARTIFACTS': [], 'REQUIRED-GENERATOR-TOOLS': []}), 'file1 must only hold Gen1'
    assert (AutosarModelTestHelper.slot_contents(file2) == {'GENERATED-ARTIFACTS': [], 'REQUIRED-ARTIFACTS': ['Req2'], 'REQUIRED-GENERATOR-TOOLS': ['Tool2']}), 'file2 must hold Req2 and Tool2'

    teardown(deleteTempDir=False)

    # Read the saved files again and confirm that everything is back in the right slot
    autosarfactory.read([file1, file2])
    impl = autosarfactory.get_node('/P/Impl')
    assert (AutosarModelTestHelper.names(impl.get_generatedArtifacts()) == ['Gen1']), 're-read generatedArtifacts'
    assert (AutosarModelTestHelper.names(impl.get_requiredArtifacts()) == ['Req2']), 're-read requiredArtifacts'
    assert (AutosarModelTestHelper.names(impl.get_requiredGeneratorTools()) == ['Tool2']), 're-read requiredGeneratorTools'

    teardown()

def test_model_move_element_to_another_parent_detaches_from_old_parent():
    """
    Tests that an element which is added to another parent is removed from its previous parent.
    """
    filePath = os.path.join(str(_create_temp_dir()), 'move.arxml')
    root = autosarfactory.new_file(filePath, defaultArPackage='P1', overWrite=True)
    package2 = root.new_ARPackage('P2')
    swc = root.new_ApplicationSwComponentType('Swc')
    assert (AutosarModelTestHelper.names(root.get_elements()) == ['Swc']), 'Swc is created under P1'

    # Read the file manually and return the elements held directly by P1 and by P2
    def swcs_in_packages():
        tree = etree.parse(filePath, etree.XMLParser(remove_blank_text=True))
        p1 = tree.find('.//{*}AR-PACKAGES/{*}AR-PACKAGE')
        p2 = p1.find('{*}AR-PACKAGES/{*}AR-PACKAGE')
        names = lambda package: [e.find('{*}SHORT-NAME').text for e in package.findall('{*}ELEMENTS/{*}APPLICATION-SW-COMPONENT-TYPE')]
        return names(p1), names(p2), len(tree.findall('.//{*}APPLICATION-SW-COMPONENT-TYPE'))

    # Save before moving, so that Swc already exists in the xml of P1
    autosarfactory.save()
    assert (swcs_in_packages() == (['Swc'], [], 1)), 'Swc is saved under P1'

    package2.add_element(swc)

    assert (root.get_elements() == []), 'Swc must no longer be an element of P1'
    assert (AutosarModelTestHelper.names(package2.get_elements()) == ['Swc']), 'Swc must be an element of P2'
    assert (swc.get_parent() is package2), 'parent of Swc must be P2'
    assert (swc.autosar_path == '/P1/P2/Swc'), 'path must be updated'

    autosarfactory.save()

    # Read saved xml manually and see if Swc is moved, and not duplicated
    assert (swcs_in_packages() == ([], ['Swc'], 1)), 'Swc must be saved under P2 only, and must exist only once'

    teardown()

def test_model_fragments_clear_singular_child_via_merged_node_saved_to_fragment_file():
    """
    Tests that clearing a single valued child through the merged node is saved to the file which holds the child.
    The merged node is built from file1, but the child (MC-SUPPORT) exists only in file2, so the fragment of file2
    must be marked as modified, even though the call is made on the merged node.
    """
    template = '''<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR xmlns="http://autosar.org/schema/r4.0">
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>P</SHORT-NAME>
      <ELEMENTS>
        <SWC-IMPLEMENTATION>
          <SHORT-NAME>Impl</SHORT-NAME>{content}
        </SWC-IMPLEMENTATION>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>'''
    tempDir = _create_temp_dir()
    file1, file2 = os.path.join(tempDir, 'mc1.arxml'), os.path.join(tempDir, 'mc2.arxml')
    with open(file1, 'w') as f:
        f.write(template.format(content=''))
    with open(file2, 'w') as f:
        f.write(template.format(content='\n          <MC-SUPPORT/>'))

    # Read the file manually and tell if it contains MC-SUPPORT
    def has_mc_support(file):
        return etree.parse(file, etree.XMLParser(remove_blank_text=True)).find('.//{*}MC-SUPPORT') is not None

    assert (not has_mc_support(file1)), 'file1 does not contain MC-SUPPORT'
    assert (has_mc_support(file2)), 'file2 contains MC-SUPPORT'

    autosarfactory.read([file1, file2])
    impl = autosarfactory.get_node('/P/Impl')
    fragment2 = impl.get_fragment(file2)
    assert (impl.file == file1), 'the merged node is built from file1'
    assert (impl.get_mcSupport() is not None), 'merged node must have the mcSupport that exists in file2'
    assert (impl.get_mcSupport().file == file2), 'mcSupport belongs to file2'
    assert (fragment2.get_mcSupport() is impl.get_mcSupport()), 'fragment of file2 holds the same mcSupport'

    # Clear the child through the merged node, though it is held by the fragment of file2.
    impl.set_mcSupport(None)
    assert (impl.get_mcSupport() is None), 'mcSupport must be cleared in the merged node'
    assert (fragment2.get_mcSupport() is None), 'mcSupport must be cleared in the fragment as well'

    autosarfactory.save()

    # Read saved xml manually and see if MC-SUPPORT is removed from file2, and file1 is left alone
    assert (not has_mc_support(file2)), 'MC-SUPPORT must be removed from file2'
    assert (not has_mc_support(file1)), 'file1 must be unchanged'

    teardown(deleteTempDir=False)

    # Read the saved files again and confirm that the mcSupport is gone
    autosarfactory.read([file1, file2])
    assert (autosarfactory.get_node('/P/Impl').get_mcSupport() is None), 're-read model must not have the mcSupport'

    teardown()

def test_model_registry_after_rename():
    """
    Tests that a renamed element, its children and the nodes which refer to it are found at the new path only.
    """
    tempDir = _create_temp_dir()
    file = AutosarModelTestHelper.write_arxml(tempDir, 'rename.arxml', AutosarModelTestHelper.swc_packages('P', 'Other'))
    autosarfactory.read([file])

    swc = autosarfactory.get_node('/P/Swc')
    swc.set_shortName('SwcNew')

    assert (swc.name == 'SwcNew'), 'name must be updated'
    assert (swc.autosar_path == '/P/SwcNew'), 'path must be updated'
    assert (autosarfactory.get_node('/P/SwcNew') is swc), 'the element must be found at the new path'
    assert (autosarfactory.get_node('/P/Swc') is None), 'the old path must not resolve any more'

    # renaming the parent changes the path of every descendant
    package = autosarfactory.get_node('/P')
    port = swc.new_PPortPrototype('port1')
    package.set_shortName('PNew')
    assert (port.autosar_path == '/PNew/SwcNew/port1'), 'descendants must follow the renamed parent'
    assert (autosarfactory.get_node('/PNew/SwcNew/port1') is port), 'descendants must be found at the new path'
    assert (autosarfactory.get_node('/P/SwcNew/port1') is None), 'old path of the descendant must not resolve'

    teardown()

def test_model_registry_after_move_and_remove():
    """
    - Tests that a moved element and all of its descendants are found at their new paths.
    - Tests that a removed element can no longer be found.
    """
    tempDir = _create_temp_dir()
    file = AutosarModelTestHelper.write_arxml(tempDir, 'move_remove.arxml',
                        '<AR-PACKAGE><SHORT-NAME>A</SHORT-NAME><AR-PACKAGES><AR-PACKAGE><SHORT-NAME>B</SHORT-NAME><ELEMENTS>'
                        '<APPLICATION-SW-COMPONENT-TYPE><SHORT-NAME>Leaf</SHORT-NAME></APPLICATION-SW-COMPONENT-TYPE>'
                        '</ELEMENTS></AR-PACKAGE></AR-PACKAGES></AR-PACKAGE><AR-PACKAGE><SHORT-NAME>Dest</SHORT-NAME></AR-PACKAGE>')
    autosarfactory.read([file])

    # moving a package moves everything below it, not only its direct children
    leaf = autosarfactory.get_node('/A/B/Leaf')
    autosarfactory.get_node('/Dest').add_arPackage(autosarfactory.get_node('/A'))
    assert (leaf.autosar_path == '/Dest/A/B/Leaf'), 'a descendant two levels down must follow the move'
    assert (autosarfactory.get_node('/Dest/A/B/Leaf') is leaf), 'must be found at the new path'
    assert (autosarfactory.get_node('/A/B/Leaf') is None), 'must not be found at the old path'

    # remove an element, then create a new one with the same name
    package = autosarfactory.get_node('/Dest/A/B')
    package.remove_element(leaf)
    assert (autosarfactory.get_node('/Dest/A/B/Leaf') is None), 'a removed element must not be found'
    newLeaf = package.new_ApplicationSwComponentType('Leaf')
    assert (autosarfactory.get_node('/Dest/A/B/Leaf') is newLeaf), 'the new element must be the one found, not the removed one'

    teardown()

def test_model_rename_and_move_are_saved():
    """
    - Tests that rename and move end up in the file. 
    - Tests the updated value of element is saved before it was renamed or moved.
    """
    tempDir = _create_temp_dir()

    # rename
    file = AutosarModelTestHelper.write_arxml(tempDir, 'rename_only.arxml', AutosarModelTestHelper.swc_packages('Other', 'P'))
    autosarfactory.read([file])
    autosarfactory.get_node('/P/Swc').set_shortName('SwcNew')
    autosarfactory.save()
    assert (AutosarModelTestHelper.swcs_in_file(file) == [('SwcNew', 'P')]), 'renamed in place'
    teardown(deleteTempDir=False)

    # rename, then move
    file = AutosarModelTestHelper.write_arxml(tempDir, 'rename_move.arxml', AutosarModelTestHelper.swc_packages('Other', 'P'))
    autosarfactory.read([file])
    swc = autosarfactory.get_node('/P/Swc')
    swc.set_shortName('SwcNew')
    autosarfactory.get_node('/Other').add_element(swc)
    autosarfactory.save()
    assert (AutosarModelTestHelper.swcs_in_file(file) == [('SwcNew', 'Other')]), 'renamed and moved'
    teardown(deleteTempDir=False)

    # move, then rename
    file = AutosarModelTestHelper.write_arxml(tempDir, 'move_rename.arxml', AutosarModelTestHelper.swc_packages('Other', 'P'))
    autosarfactory.read([file])
    swc = autosarfactory.get_node('/P/Swc')
    autosarfactory.get_node('/Other').add_element(swc)
    swc.set_shortName('SwcNew')
    autosarfactory.save()
    assert (AutosarModelTestHelper.swcs_in_file(file) == [('SwcNew', 'Other')]), 'moved and renamed'
    teardown(deleteTempDir=False)

    # modified first, then moved
    file = AutosarModelTestHelper.write_arxml(tempDir, 'modify_move.arxml', AutosarModelTestHelper.swc_packages('Other', 'P'))
    autosarfactory.read([file])
    swc = autosarfactory.get_node('/P/Swc')
    swc.set_category('CAT')
    autosarfactory.get_node('/Other').add_element(swc)
    autosarfactory.save()
    assert (AutosarModelTestHelper.swcs_in_file(file) == [('Swc', 'Other')]), 'must be saved under the new parent although it was modified before'
    category = etree.parse(file).find('.//{*}APPLICATION-SW-COMPONENT-TYPE/{*}CATEGORY')
    assert (category is not None and category.text == 'CAT'), 'the earlier modification must be saved too'
    teardown(deleteTempDir=False)

    # a child modified first, then its ancestor renamed
    file = AutosarModelTestHelper.write_arxml(tempDir, 'child_rename.arxml',
                        '<AR-PACKAGE><SHORT-NAME>P</SHORT-NAME><ELEMENTS><APPLICATION-SW-COMPONENT-TYPE><SHORT-NAME>Swc</SHORT-NAME>'
                        '<INTERNAL-BEHAVIORS><SWC-INTERNAL-BEHAVIOR><SHORT-NAME>Beh</SHORT-NAME><RUNNABLES><RUNNABLE-ENTITY><SHORT-NAME>Run</SHORT-NAME>'
                        '</RUNNABLE-ENTITY></RUNNABLES></SWC-INTERNAL-BEHAVIOR></INTERNAL-BEHAVIORS></APPLICATION-SW-COMPONENT-TYPE></ELEMENTS></AR-PACKAGE>')
    autosarfactory.read([file])
    autosarfactory.get_node('/P/Swc/Beh/Run').set_canBeInvokedConcurrently(True)
    autosarfactory.get_node('/P/Swc').set_shortName('SwcNew')
    autosarfactory.save()
    concurrently = etree.parse(file).find('.//{*}CAN-BE-INVOKED-CONCURRENTLY')
    assert (concurrently is not None and concurrently.text == 'true'), 'a change made before renaming an ancestor must not be lost'

    teardown()

def test_model_references_follow_rename_and_move():
    """
    - Tests that references to a renamed or moved element are saved with its new path
    - Tests also in a node which was not modified, and that the reference resolves again when the files are re-read.
    """
    tempDir = _create_temp_dir()
    ref = '<DATA-TYPE-MAPPING-REF DEST="DATA-TYPE-MAPPING-SET">{}</DATA-TYPE-MAPPING-REF>'
    targets = ('<AR-PACKAGE><SHORT-NAME>Maps</SHORT-NAME><ELEMENTS>'
               '<DATA-TYPE-MAPPING-SET><SHORT-NAME>Ok1</SHORT-NAME></DATA-TYPE-MAPPING-SET>'
               '<DATA-TYPE-MAPPING-SET><SHORT-NAME>Ok2</SHORT-NAME></DATA-TYPE-MAPPING-SET>'
               '<APPLICATION-SW-COMPONENT-TYPE><SHORT-NAME>SwcOk</SHORT-NAME></APPLICATION-SW-COMPONENT-TYPE></ELEMENTS></AR-PACKAGE>'
               '<AR-PACKAGE><SHORT-NAME>Other</SHORT-NAME></AR-PACKAGE>')
    user = ('<AR-PACKAGE><SHORT-NAME>P</SHORT-NAME><ELEMENTS><COMPOSITION-SW-COMPONENT-TYPE><SHORT-NAME>A</SHORT-NAME><COMPONENTS>'
            '<SW-COMPONENT-PROTOTYPE><SHORT-NAME>Proto</SHORT-NAME><TYPE-TREF DEST="APPLICATION-SW-COMPONENT-TYPE">/Maps/SwcOk</TYPE-TREF></SW-COMPONENT-PROTOTYPE>'
            '</COMPONENTS><DATA-TYPE-MAPPING-REFS>' + ref.format('/Maps/Ok1') + ref.format('/Maps/Ok2') + '</DATA-TYPE-MAPPING-REFS>'
            '</COMPOSITION-SW-COMPONENT-TYPE></ELEMENTS></AR-PACKAGE>')
    
    targetsFile = AutosarModelTestHelper.write_arxml(tempDir, 'targets.arxml', targets)
    userFile = AutosarModelTestHelper.write_arxml(tempDir, 'user.arxml', user)

    def refs_in_file():
        tree = etree.parse(userFile)
        listRefs = [e.text for e in tree.findall('.//{*}DATA-TYPE-MAPPING-REF')]
        singleRef = tree.find('.//{*}TYPE-TREF')
        return listRefs, singleRef.text

    autosarfactory.read([targetsFile, userFile])
    # the referencing nodes are not touched at all, only the targets change
    autosarfactory.get_node('/Maps/Ok1').set_shortName('Ok1New')
    autosarfactory.get_node('/Other').add_element(autosarfactory.get_node('/Maps/SwcOk'))
    autosarfactory.save()
    assert (refs_in_file() == (['/Maps/Ok1New', '/Maps/Ok2'], '/Other/SwcOk')), 'references must be saved with the new paths'
    teardown(deleteTempDir=False)

    # read again and confirm that the references resolve to the changed targets
    autosarfactory.read([targetsFile, userFile])
    comp = autosarfactory.get_node('/P/A')
    assert ([m.name for m in comp.get_dataTypeMappings()] == ['Ok1New', 'Ok2']), 'list references must resolve'
    assert (all(not m.is_proxy() for m in comp.get_dataTypeMappings())), 'none of them may be a proxy'
    proto = autosarfactory.get_node('/P/A/Proto')
    assert (proto.get_type().is_proxy() is False and proto.get_type().name == 'SwcOk'), 'Must be the SwcType'

    teardown()

def test_model_remove_reference_after_target_rename_or_move():
    """
    Tests that an entry can be removed from a reference list after the referenced element was renamed or moved, and that the removal ends up in the file.
    """
    tempDir = _create_temp_dir()
    ref = '<DATA-TYPE-MAPPING-REF DEST="DATA-TYPE-MAPPING-SET">{}</DATA-TYPE-MAPPING-REF>'
    body = ('<AR-PACKAGE><SHORT-NAME>Maps</SHORT-NAME><ELEMENTS>'
            '<DATA-TYPE-MAPPING-SET><SHORT-NAME>Ok1</SHORT-NAME></DATA-TYPE-MAPPING-SET>'
            '<DATA-TYPE-MAPPING-SET><SHORT-NAME>Ok2</SHORT-NAME></DATA-TYPE-MAPPING-SET></ELEMENTS></AR-PACKAGE>'
            '<AR-PACKAGE><SHORT-NAME>Other</SHORT-NAME></AR-PACKAGE>'
            '<AR-PACKAGE><SHORT-NAME>P</SHORT-NAME><ELEMENTS><COMPOSITION-SW-COMPONENT-TYPE><SHORT-NAME>A</SHORT-NAME><COMPONENTS/>'
            '<DATA-TYPE-MAPPING-REFS>' + ref.format('/Maps/Ok1') + ref.format('/Maps/Ok2') + '</DATA-TYPE-MAPPING-REFS>'
            '</COMPOSITION-SW-COMPONENT-TYPE></ELEMENTS></AR-PACKAGE>')
    file = AutosarModelTestHelper.write_arxml(tempDir, 'remove_ref.arxml', body)
    autosarfactory.read([file])

    comp = autosarfactory.get_node('/P/A')
    ok1, ok2 = autosarfactory.get_node('/Maps/Ok1'), autosarfactory.get_node('/Maps/Ok2')
    ok1.set_shortName('Ok1New')                       # renamed
    autosarfactory.get_node('/Other').add_element(ok2)  # moved

    # The references follow the renamed / moved elements.
    assert ([m.autosar_path for m in comp.get_dataTypeMappings()] == ['/Maps/Ok1New', '/Other/Ok2']), 'the references must report the new paths'
    assert (autosarfactory.get_node('/Maps/Ok1New') is ok1 and autosarfactory.get_node('/Other/Ok2') is ok2), 'must be found at the new paths'
    assert (autosarfactory.get_node('/Maps/Ok1') is None and autosarfactory.get_node('/Maps/Ok2') is None), 'must not be found at the old paths'
    assert (comp in ok1.referenced_by and comp in ok2.referenced_by), 'the referrer must still be registered with both targets'

    comp.remove_dataTypeMapping(ok1)
    assert (ok2 in comp.get_dataTypeMappings() and ok1 not in comp.get_dataTypeMappings()), 'only the renamed one is removed'
    comp.remove_dataTypeMapping(ok2)
    assert (comp.get_dataTypeMappings() == []), 'dataTypeMapping must be empty'
    assert (comp not in ok1.referenced_by and comp not in ok2.referenced_by), 'the referrer must be unregistered from both targets'

    autosarfactory.save()
    assert ([e.text for e in etree.parse(file).findall('.//{*}DATA-TYPE-MAPPING-REF')] == []), 'both references must be removed from the file'

    teardown()

def test_create_model_elements_from_constructor():
    """
    Tests if the model elements are created as expected using the CTor
    """
    filePath = os.path.join(resourcesDir, 'newFileCreateModelElementFromCTor.arxml')
    arPackage = autosarfactory.new_file(filePath,overWrite=True,defaultArPackage='myPack')
    
    swc = autosarfactory.ApplicationSwComponentType()
    swc.set_shortName('swc')
    arPackage.add_element(swc)

    interface = autosarfactory.SenderReceiverInterface()
    interface.set_shortName('if')
    arPackage.add_element(interface)

    port = autosarfactory.PPortPrototype()
    port.set_shortName('port')
    swc.add_port(port)
    port.set_providedInterface(interface)

    autosarfactory.save()
    teardown(deleteTempDir=False)

    # read the created file and see if the contents exists
    autosarfactory.read([os.path.join(resourcesDir, 'newFileCreateModelElementFromCTor.arxml')])
    swcFromFile:autosarfactory.ApplicationSwComponentType = autosarfactory.get_node('/myPack/swc')
    assert (swcFromFile is not None)
    assert (len(swcFromFile.get_ports()) == 1)
    assert (swcFromFile.get_ports()[0].get_shortName() == 'port')
    assert (swcFromFile.get_ports()[0].get_providedInterface().get_shortName() == 'if')
    teardown()

def test_model_set_short_name_using_factory_method():
    """
    Tests if the short name is set properly when the factory method is used to create child elements under the node.
    This regression is due to the case that the short name was not getting set after the XmldirtyTracker was introduced
    """
    componentArxml = os.path.join(resourcesDir, 'components.arxml')
    tempDir = _create_temp_dir()
    tempComponentArxml = os.path.join(tempDir, 'components.arxml')
    shutil.copy(componentArxml, tempDir)

    autosarfactory.read([tempComponentArxml])
    autosarfactory.get_node('/Swcs').new_DiagnosticRoutine('dRoutine').new_RequestResult('reqRes')
    autosarfactory.save()
    autosarfactory.reinit()

    # Read back the file and see if the element is created
    autosarfactory.read([tempComponentArxml])
    assert (autosarfactory.get_node('/Swcs/dRoutine/reqRes') is not None)
    teardown()
