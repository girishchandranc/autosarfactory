import os, sys
mod_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, mod_path)
from autosarmodeller import autosarmodeller

generatdDir = os.path.join(os.path.dirname(__file__), 'generated')
dataTypesFile = os.path.join(generatdDir, 'dataTypes.arxml')
interfaceFile = os.path.join(generatdDir, 'interface.arxml')
componentsFile = os.path.join(generatdDir, 'components.arxml')
canNetworkFile = os.path.join(generatdDir, 'CanNetwork.arxml')
mergedFile = os.path.join(generatdDir, 'merged.arxml')

dtPack = autosarmodeller.create_new_file(dataTypesFile, defaultArPackage = 'DataTypes', overWrite = True)
baseTypePack = dtPack.create_ARPackage('baseTypes')
uint8BaseType = baseTypePack.create_SwBaseType('uint8')

implTypePack = dtPack.create_ARPackage('ImplTypes')
uint8 = implTypePack.create_ImplementationDataType('uint8')
uint8.create_SwDataDefProps().create_SwDataDefPropsVariant().set_baseType(uint8BaseType)

ifPack = autosarmodeller.create_new_file(interfaceFile, defaultArPackage = 'Interfaces', overWrite = True)
srIf = ifPack.create_SenderReceiverInterface('srif1')
vdp = srIf.create_DataElement('de1')
vdp.set_type(uint8)
vdp.create_NumericalValueSpecification().create_Value().set('1')

swcPack = autosarmodeller.create_new_file(componentsFile, defaultArPackage = 'Swcs', overWrite = True)
asw1 = swcPack.create_ApplicationSwComponentType('asw1')
port1 = asw1.create_PPortPrototype('outPort')
port1.set_providedInterface(srIf)

beh1 = asw1.create_InternalBehavior('beh1')
te1 = beh1.create_TimingEvent('te_5ms')
te1.set_period(0.005)

run1 = beh1.create_Runnable('Runnable_1')
run1.set_symbol('Run1')
te1.set_startOnEvent(run1)

dsp = run1.create_DataSendPoint('dsp')
var = dsp.create_AccessedVariable().create_AutosarVariable()
var.set_portPrototype(port1)
var.set_targetDataPrototype(vdp)

asw2 = swcPack.create_ApplicationSwComponentType('asw2')
port2 = asw2.create_RPortPrototype('inPort')
port2.set_requiredInterface(srIf)

beh2 = asw2.create_InternalBehavior('beh1')
dre = beh2.create_DataReceivedEvent('DRE_Vdp')
data = dre.create_Data()
data.set_contextRPort(port2)
data.set_targetDataElement(vdp)

run2 = beh2.create_Runnable('Runnable_2')
run2.set_symbol('Run2')
dre.set_startOnEvent(run2)

dra = run2.create_DataReceivePointByArgument('dra')
var_dra = dra.create_AccessedVariable().create_AutosarVariable()
var_dra.set_portPrototype(port2)
var_dra.set_targetDataPrototype(vdp)

# composition and connectors.
composition = swcPack.create_CompositionSwComponentType('Comp')
asw1_proto = composition.create_Component('asw1_proto')
asw2_proto = composition.create_Component('asw2_proto')
asw1_proto.set_type(asw1)
asw2_proto.set_type(asw2)

conn1 = composition.create_AssemblySwConnector('conn1')
provider = conn1.create_Provider()
provider.set_contextComponent(asw1_proto)
provider.set_targetPPort(port1)
required = conn1.create_Requester()
required.set_contextComponent(asw2_proto)
required.set_targetRPort(port2)

canNetworkPack = autosarmodeller.create_new_file(canNetworkFile, defaultArPackage = 'Can', overWrite = True)
signalsPack = canNetworkPack.create_ARPackage('signals')
systemsignalsPack = canNetworkPack.create_ARPackage('systemsignals')
syssig1 = systemsignalsPack.create_SystemSignal('syssig1')

sig1 = signalsPack.create_ISignal('sig1')
sig1.set_length(4)
sig1.set_dataTypePolicy(autosarmodeller.DataTypePolicyEnum.VALUE_LEGACY)
sig1.set_iSignalType(autosarmodeller.ISignalTypeEnum.VALUE_PRIMITIVE)
sig1.set_systemSignal(syssig1)

ecuPack = canNetworkPack.create_ARPackage('ecus')
ecu1 = ecuPack.create_EcuInstance('ecu1')

sysPack = canNetworkPack.create_ARPackage('system')
system = sysPack.create_System('CanSystem')
sysMapping = system.create_Mapping('Mappings')
srMapping = sysMapping.create_SenderReceiverToSignalMapping('outportToSig1Mapping')
srMapping.set_systemSignal(syssig1)
mapDe = srMapping.create_DataElement()
mapDe.set_contextPort(port1)
mapDe.set_targetDataPrototype(vdp)

rootComp = system.create_RootSoftwareComposition('rootSwcom')
rootComp.set_softwareComposition(composition)

swctoEcuMp = sysMapping.create_SwMapping('SwcMapping')
swctoEcuMp.set_ecuInstance(ecu1)
swcMap1 = swctoEcuMp.create_Component()
swcMap1.set_contextComposition(rootComp)
swcMap1.add_contextComponent(asw1_proto)
swcMap1.add_contextComponent(asw2_proto)

autosarmodeller.save()
autosarmodeller.saveAs(mergedFile, overWrite = True)