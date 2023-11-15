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

def teardown():
    """ teardown any state that was previously setup.
    """
    autosarfactory.reinit()
    assert (autosarfactory.get_root() is None), 'Root should be None'

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
    tempDir = os.path.join(resourcesDir,"temp")
    tempComponentArxml = os.path.join(tempDir, 'components.arxml')

    os.mkdir(tempDir)
    shutil.copy(componentArxml, tempDir)

    autosarfactory.save()
    assert (filecmp.cmp(componentArxml, tempComponentArxml) is False), "files should be different"

    #copy back the originalfile
    shutil.copy(tempComponentArxml, resourcesDir)
    shutil.rmtree(tempDir)
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
    tempDir = os.path.join(resourcesDir,"temp")
    tempComponentArxml = os.path.join(tempDir, 'components.arxml')

    try:
        os.mkdir(tempDir)
    except:
        pass
    shutil.copy(componentArxml, tempDir)

    autosarfactory.save()
    teardown()

    autosarfactory.read([componentArxml])
    te = autosarfactory.get_node('/Swcs/asw1/beh1/te_5ms')
    assert (te is not None), 'te should not be None'
    assert(te.get_period() == 2000), 'value of period should be 2000'
    
    #copy back the originalfile
    shutil.copy(tempComponentArxml, resourcesDir)
    shutil.rmtree(tempDir)
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
    teardown()

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
    teardown()

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
    teardown()

    # Read saved xml manually and see if the elements are removed
    tree = etree.parse(os.path.join(resourcesDir, 'components.arxml'), etree.XMLParser(remove_blank_text=True))
    arpackages = tree.findall(".//{*}AR-PACKAGE")
    for pack in arpackages:
        if pack.find('{*}SHORT-NAME').text == 'Swcs':
            assert(len(pack.findall(".//{*}APPLICATION-SW-COMPONENT-TYPE")) == 1), 'only one swc expected in the arpackage path /Swcs/Swcs_hierarchy1/Swcs_hierarchy2/asw123. Ones inside Swcs package are removed'
            assert(len(pack.findall(".//{*}COMPOSITION-SW-COMPONENT-TYPE")) == 0), 'no composition expected as its already removed'
            assert(len(pack.findall(".//{*}SYSTEM")) == 0), 'no system expected as its already removed'
            break

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
    teardown()

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
