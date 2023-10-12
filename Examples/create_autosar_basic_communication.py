import os, sys
mod_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, mod_path)
from autosarfactory import autosarfactory


def __createCompuScales(compuScales, lowerLimitVal, upperLimitVal, constVal):
    compuScale = compuScales.new_CompuScale()
    compuScale.new_CompuScaleConstantContents().new_CompuConst().new_CompuConstTextContent().set_vt(constVal)

    upperLimit = compuScale.new_UpperLimit()
    upperLimit.set(upperLimitVal)
    upperLimit.set_intervalType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)

    lowerLimit = compuScale.new_LowerLimit()
    lowerLimit.set(lowerLimitVal)
    lowerLimit.set_intervalType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)


generatdDir = os.path.join(os.path.dirname(__file__), 'generated')
dataTypesFile = os.path.join(generatdDir, 'dataTypes.arxml')
interfaceFile = os.path.join(generatdDir, 'interface.arxml')
componentsFile = os.path.join(generatdDir, 'components.arxml')
canNetworkFile = os.path.join(generatdDir, 'CanNetwork.arxml')
mergedFile = os.path.join(generatdDir, 'merged.arxml')

dtPack = autosarfactory.new_file(dataTypesFile, defaultArPackage = 'DataTypes', overWrite = True)
baseTypePack = dtPack.new_ARPackage('baseTypes')
uint8BaseType = baseTypePack.new_SwBaseType('uint8')
baseTypeDef = uint8BaseType.new_BaseTypeDirectDefinition()
baseTypeDef.set_baseTypeEncoding('2C')
baseTypeDef.set_nativeDeclaration('unsigned char')
baseTypeDef.set_memAlignment(8)
baseTypeDef.set_baseTypeSize(16)

compuPack = dtPack.new_ARPackage('compuMethods')
compu1 = compuPack.new_CompuMethod('cm1')
intoPhy = compu1.new_CompuInternalToPhys()
compuScales  = intoPhy.new_CompuScales()

__createCompuScales(compuScales=compuScales, lowerLimitVal=0, upperLimitVal=0, constVal='ECU_STATE_STOP')
__createCompuScales(compuScales=compuScales, lowerLimitVal=1, upperLimitVal=1, constVal='ECU_STATE_START')
__createCompuScales(compuScales=compuScales, lowerLimitVal=2, upperLimitVal=2, constVal='ECU_STATE_RUN')

# Create a compu method for rational coeffs
compu2 = compuPack.new_CompuMethod('cm2')
rationalCoeff = compu2.new_CompuInternalToPhys().new_CompuScales().new_CompuScale().new_CompuScaleRationalFormula().new_CompuRationalCoeffs()
num = rationalCoeff.new_CompuNumerator()
num.new_V().set(100)
num.new_V().set(200)
num.new_V().set(300)

dataConstrPack = dtPack.new_ARPackage('dataConstrs')
dataConstr = dataConstrPack.new_DataConstr('dc1')
intConstr = dataConstr.new_DataConstrRule().new_InternalConstrs()

dcLowerLimit = intConstr.new_LowerLimit()
dcLowerLimit.set(-128)
dcLowerLimit.set_intervalType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)

dcUpperLimit = intConstr.new_UpperLimit()
dcUpperLimit.set(127)
dcUpperLimit.set_intervalType(autosarfactory.IntervalTypeEnum.VALUE_CLOSED)


implTypePack = dtPack.new_ARPackage('ImplTypes')
uint8 = implTypePack.new_ImplementationDataType('uint8')
variant = uint8.new_SwDataDefProps().new_SwDataDefPropsVariant()
variant.set_baseType(uint8BaseType)
variant.set_compuMethod(compu1)
variant.set_dataConstr(dataConstr)

ifPack = autosarfactory.new_file(interfaceFile, defaultArPackage = 'Interfaces', overWrite = True)
srIf = ifPack.new_SenderReceiverInterface('srif1')
vdp = srIf.new_DataElement('de1')
vdp.set_type(uint8)
vdp.new_NumericalValueSpecification().new_Value().set('1')

swcPack = autosarfactory.new_file(componentsFile, defaultArPackage = 'Swcs', overWrite = True)
asw1 = swcPack.new_ApplicationSwComponentType('asw1')
port1 = asw1.new_PPortPrototype('outPort')
port1.set_providedInterface(srIf)

beh1 = asw1.new_InternalBehavior('beh1')
te1 = beh1.new_TimingEvent('te_5ms')
te1.set_period(0.005)

run1 = beh1.new_Runnable('Runnable_1')
run1.set_symbol('Run1')
te1.set_startOnEvent(run1)

dsp = run1.new_DataSendPoint('dsp')
var = dsp.new_AccessedVariable().new_AutosarVariable()
var.set_portPrototype(port1)
var.set_targetDataPrototype(vdp)

asw2 = swcPack.new_ApplicationSwComponentType('asw2')
port2 = asw2.new_RPortPrototype('inPort')
port2.set_requiredInterface(srIf)

beh2 = asw2.new_InternalBehavior('beh1')
dre = beh2.new_DataReceivedEvent('DRE_Vdp')
data = dre.new_Data()
data.set_contextRPort(port2)
data.set_targetDataElement(vdp)

run2 = beh2.new_Runnable('Runnable_2')
run2.set_symbol('Run2')
dre.set_startOnEvent(run2)

dra = run2.new_DataReceivePointByArgument('dra')
var_dra = dra.new_AccessedVariable().new_AutosarVariable()
var_dra.set_portPrototype(port2)
var_dra.set_targetDataPrototype(vdp)

# composition and connectors.
composition = swcPack.new_CompositionSwComponentType('Comp')
asw1_proto = composition.new_Component('asw1_proto')
asw2_proto = composition.new_Component('asw2_proto')
asw1_proto.set_type(asw1)
asw2_proto.set_type(asw2)

conn1 = composition.new_AssemblySwConnector('conn1')
provider = conn1.new_Provider()
provider.set_contextComponent(asw1_proto)
provider.set_targetPPort(port1)
required = conn1.new_Requester()
required.set_contextComponent(asw2_proto)
required.set_targetRPort(port2)

canNetworkPack = autosarfactory.new_file(canNetworkFile, defaultArPackage = 'Can', overWrite = True)
signalsPack = canNetworkPack.new_ARPackage('signals')
systemsignalsPack = canNetworkPack.new_ARPackage('systemsignals')
syssig1 = systemsignalsPack.new_SystemSignal('syssig1')
syssig1.set_dynamicLength(True)

sig1 = signalsPack.new_ISignal('sig1')
sig1.set_systemSignal(syssig1)
sig1.set_length(4)
sig1.set_dataTypePolicy(autosarfactory.DataTypePolicyEnum.VALUE_LEGACY)
sig1.set_iSignalType(autosarfactory.ISignalTypeEnum.VALUE_PRIMITIVE)

ecuPack = canNetworkPack.new_ARPackage('ecus')
ecu1 = ecuPack.new_EcuInstance('ecu1')
ecu1.set_wakeUpOverBusSupported(True)
ecu1.set_sleepModeSupported(False)

sysPack = canNetworkPack.new_ARPackage('system')
system = sysPack.new_System('CanSystem')
sysMapping = system.new_Mapping('Mappings')
srMapping = sysMapping.new_SenderReceiverToSignalMapping('outportToSig1Mapping')
srMapping.set_systemSignal(syssig1)
mapDe = srMapping.new_DataElement()
mapDe.set_contextPort(port1)
mapDe.set_targetDataPrototype(vdp)

rootComp = system.new_RootSoftwareComposition('rootSwcom')
rootComp.set_softwareComposition(composition)

swctoEcuMp = sysMapping.new_SwMapping('SwcMapping')
swctoEcuMp.set_ecuInstance(ecu1)
swcMap1 = swctoEcuMp.new_Component()
swcMap1.set_contextComposition(rootComp)
swcMap1.add_contextComponent(asw1_proto)
swcMap1.add_contextComponent(asw2_proto)
swcMap1.set_targetComponent(asw1_proto)

autosarfactory.save()
autosarfactory.saveAs(mergedFile, overWrite = True)