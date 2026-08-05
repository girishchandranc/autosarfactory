## AUTOSAR element map by use case

### Sender-Receiver communication (SWC to SWC, same ECU)
depends_on: Data types
  SenderReceiverInterface, VariableDataPrototype (data element)
    VariableDataPrototype.set_Type() MUST reference an ApplicationDataType or ImplementationDataType — NOT SwBaseType.
    SwBaseType is a primitive C type only; use ApplicationPrimitiveDataType for scalars,
    ApplicationRecordDataType for structs, ApplicationArrayDataType for arrays.
    Use ApplicationDataType when user explicitly wants it or else use ImplementationDataType
    See the "Data types" section (automatically included) for the full creation chain.
  ApplicationSwComponentType with PPortPrototype (sender) and RPortPrototype (receiver)
  SwcInternalBehavior, RunnableEntity, TimingEvent
  DataSendPoint (sender runnable), DataReceivePoint (receiver runnable)
  CompositionSwComponentType to assemble both SWCs

### Send signal from SWC over CAN bus
depends_on: Sender-Receiver communication (SWC to SWC, same ECU)
  All of Sender-Receiver above and create delegationconnector
  instead of the assembly connection in CompositionSwComponentType, plus:
  SystemSignal, ISignal (length in bits)
  ISignalIPdu + ISignalToIPduMapping (length in bytes)
  CanFrame + PduToFrameMapping
  EcuInstance + CanCommunicationController + CanCommunicationConnector
    -> ISignalPort (OUT), IPduPort (OUT), FramePort (OUT)
  CanCluster -> CanClusterConditional (baudrate) -> CanPhysicalChannel
    -> ISignalTriggering (refs ISignal + ISignalPort)
    -> PduTriggering (refs ISignalIPdu + IPduPort + ISignalTriggering)
    -> CanFrameTriggering (refs CanFrame + FramePort + PduTriggering, has CAN ID)
  System + RootSwCompositionPrototype
  SystemMapping -> SenderReceiverToSignalMapping (SWC port -> SystemSignal)
  SystemMapping -> SwcToEcuMapping (SWC -> EcuInstance)

### Receive signal from CAN bus into SWC
depends_on: Send signal from SWC over CAN bus
  Same as above but direction reversed:
  RPortPrototype, ISignalPort/IPduPort/FramePort all IN, DataReceivePoint

### Client-Server communication (SWC to SWC)
  ClientServerInterface + OperationPrototype + ArgumentDataPrototype
  ApplicationSwComponentType with PPortPrototype (server) and RPortPrototype (client)
  Server side: RunnableEntity triggered by OperationInvokedEvent
  Client side: RunnableEntity with SynchronousServerCallPoint or AsynchronousServerCallPoint
  CompositionSwComponentType to assemble both SWCs

### Call remote server from SWC over CAN bus
depends_on: Client-Server communication (SWC to SWC)
depends_on: Send signal from SWC over CAN bus
  All of Client-Server above and create delegationconnector
  instead of the assembly connection in CompositionSwComponentType, plus:
  All of the Send signal from SWC over CAN bus from above

### Use data transformation
  A TransformerChain holds an ordered list of TransformerTechnology entries.
  The chain is created in a shared ArPackage and then referenced from the signal or signal group.

  TransformerChain (hasShortName=True, lives in a shared ArPackage)
    TransformerTechnology (one entry per transformation step, ordered)
      set_transformerClass(category)  — controls what kind of transformation is applied
        category SERIALIZER  — serialises signal data (e.g. SOME/IP payload layout)
        category SAFETY      — adds End-to-End (E2E) protection
        category SECURITY    — adds encryption / authentication

  Attaching the chain to signals:
    SOME/IP transformer  — attach to ISignal:
      ISignal -> set_transformerChain(TransformerChain)
    COM-based transformer — attach to ISignalGroup:
      ISignalGroup -> set_transformerChain(TransformerChain)

  Typical patterns:
    SOME/IP only       : one TransformerTechnology (SERIALIZER) in chain, attach to ISignal
    SOME/IP + E2E      : two entries in chain — SERIALIZER first, then SAFETY; attach to ISignal
    COM-based + E2E    : two entries in chain — SERIALIZER first, then SAFETY; attach to ISignalGroup

### Data types
  Primitive:
    SwBaseType  — primitive C type (uint8, uint16, sint32, float32, boolean...)
    ImplementationDataType (category VALUE)
      SwDataDefProps -> SwDataDefPropsConditional -> set_baseType(SwBaseType)
    ApplicationPrimitiveDataType (category VALUE)
      SwDataDefProps -> SwDataDefPropsConditional -> set_implementationDataType(ImplementationDataType)
    DataTypeMappingSet -> DataTypeMap
      set_applicationDataType(ApplicationPrimitiveDataType)
      set_implementationDataType(ImplementationDataType)

  Structure (record of named fields):
    ImplementationDataType (category STRUCTURE)
      For each field: ImplementationDataTypeElement (category VALUE, hasShortName=True)
        SwDataDefProps -> SwDataDefPropsConditional -> set_baseType(SwBaseType)
        set_arraySize() only if the field itself is a fixed-size sub-array
    ApplicationRecordDataType (category STRUCTURE)
      For each field: ApplicationRecordElement (hasShortName=True)
        set_type(matching ApplicationDataType type)
    DataTypeMappingSet -> DataTypeMap
      set_applicationDataType(ApplicationRecordDataType)
      set_implementationDataType(ImplementationDataType structure)

  Array (fixed-size sequence of same-type elements):
    ImplementationDataType (category ARRAY)
      One ImplementationDataTypeElement (category VALUE, no SHORT-NAME needed)
        set_arraySize(N)  — number of elements
        SwDataDefProps -> SwDataDefPropsConditional -> set_baseType(SwBaseType)
    ApplicationArrayDataType (category ARRAY)
      ApplicationArrayElement
        set_maxNumberOfElements(N)
        set_type(matching ApplicationDataType type)
    DataTypeMappingSet -> DataTypeMap
      set_applicationDataType(ApplicationArrayDataType)
      set_implementationDataType(ImplementationDataType array)

### Computation methods (CompuMethod)
  CompuMethod defines how an internal (raw) value maps to a physical value.
  It is attached to a data type via:
    ImplementationDataType (or ImplementationDataTypeElement)
      -> SwDataDefProps -> SwDataDefPropsConditional -> set_compuMethod(CompuMethod)

  IDENTICAL  — physical == internal (no conversion needed):
    CompuMethod (category IDENTICAL)
      No scales required.

  LINEAR  — physical = (numerator[1] * internal + numerator[0]) / denominator[0]
    e.g. temperature_C = 0.1 * raw_value - 40
    CompuMethod (category LINEAR)
      CompuInternalToPhys
        CompuScales
          CompuScale
            set_lowerLimit / set_upperLimit  — valid internal range
            CompuRationalCoeffs
              CompuNumerator   — coefficients [offset, factor]  e.g. [-40, 0.1]
              CompuDenominator — coefficients [1]

  SCALE_LINEAR  — piecewise linear (multiple CompuScale entries, each with its own range):
    CompuMethod (category SCALE_LINEAR)
      CompuInternalToPhys
        CompuScales
          CompuScale (range 1): set_lowerLimit, set_upperLimit, CompuRationalCoeffs
          CompuScale (range 2): set_lowerLimit, set_upperLimit, CompuRationalCoeffs
          ... (one CompuScale per linear segment)

  TEXTTABLE  — maps integer internal values to text labels (enumerations):
    e.g. 0->"NEUTRAL", 1->"FIRST", 2->"SECOND"
    CompuMethod (category TEXTTABLE)
      CompuInternalToPhys
        CompuScales
          CompuScale (one per label):
            set_lowerLimit(N) and set_upperLimit(N)  — same value for exact match
            CompuConst -> set_vt("LABEL_TEXT")       — the text label

### Data constraints (DataConstr)
  DataConstr defines the valid value range for a data type (internal and/or physical).
  It is attached to a data type via:
    if internal, ImplementationDataType (or ImplementationDataTypeElement)
                 -> SwDataDefProps -> SwDataDefPropsConditional -> set_dataConstraint(DataConstr)
    if physical, ApplicationDataType (or ApplicationRecordElement or ApplicationArrayElement)
                 -> SwDataDefProps -> SwDataDefPropsConditional -> set_dataConstraint(DataConstr)

  Structure:
    DataConstr (hasShortName=True, lives in a shared ArPackage)
      DataConstrRule
        InternalConstrs   — constrains the raw/internal value range
          set_lowerLimit(value)  — minimum internal value
          set_upperLimit(value)  — maximum internal value
        PhysConstrs       — constrains the physical value range (after CompuMethod)
          set_lowerLimit(value)
          set_upperLimit(value)

  Limit interval type (pass IntervalTypeEnum to set_lowerLimit / set_upperLimit):
    IntervalTypeEnum.VALUE_CLOSED   — limit value included in valid range  (<=, >=)  [default]
    IntervalTypeEnum.VALUE_OPEN     — limit value excluded from valid range (<, >)
    IntervalTypeEnum.VALUE_INFINITE — no bound in that direction (omit the limit call)

  Typical patterns:
    Bounded range    : set_lowerLimit(0),   set_upperLimit(255)    — uint8 full range if IntervalTypeEnum.VALUE_OPEN
    Open upper bound : set_lowerLimit(0),   no set_upperLimit call — unbounded above if IntervalTypeEnum.VALUE_INFINITE
    Exact value only : set_lowerLimit(N),   set_upperLimit(N)      — single valid value if IntervalTypeEnum.VALUE_CLOSED

  Note: InternalConstrs and PhysConstrs can be used independently or together.
  If only InternalConstrs is specified, physical range is inferred from the CompuMethod.
  Use PhysConstrs when the physical range must be stated explicitly.

### Init values
  An init value sets the default value of a data element at startup.
  It is set directly on the data prototype that owns the data:
    VariableDataPrototype  (in SenderReceiverInterface)
    ParameterDataPrototype (in ParameterInterface)
    ArgumentDataPrototype  (in ClientServerInterface)

  Primitive (numeric / boolean):
    dataPrototype.set_initValue() with a NumericalOrReferenceValue
      NumericalOrReferenceValue -> set_value(number)   — e.g. 0, 3.14, True(1)/False(0)

  Text (for TEXTTABLE CompuMethod values):
    dataPrototype.set_initValue() with a TextValueSpecification
      TextValueSpecification -> set_value("LABEL_TEXT")

  Array:
    dataPrototype.set_initValue() with an ArrayValueSpecification
      ArrayValueSpecification — add one NumericalOrReferenceValue per element

  Record / Structure:
    dataPrototype.set_initValue() with a RecordValueSpecification
      RecordValueSpecification — add one field value per ApplicationRecordElement,
                                 each field wrapped in a NumericalOrReferenceValue

  Note: Always call get_class('VariableDataPrototype') to confirm the exact
  set_initValue method and the correct value container class name before generating code.

### Ethernet / SOME/IP communication
depends_on: Sender-Receiver communication (SWC to SWC, same ECU)
  Ethernet network topology:
    EthernetCluster (hasShortName=True, in shared ArPackage)
      EthernetClusterConditional
        EthernetPhysicalChannel (hasShortName=True)
          NetworkEndpoint (hasShortName=True)
            set_networkEndpointAddress() with Ipv4Configuration or Ipv6Configuration
              Ipv4Configuration: set_ipv4Address("192.168.1.1"), set_networkMask("255.255.255.0")

  ECU Ethernet hardware (on EcuInstance):
    EthernetCommunicationController (hasShortName=True)
    EthernetCommunicationConnector  (hasShortName=True)
      set_commController(EthernetCommunicationController)
      set_ecu(EcuInstance)
      EthernetPhysicalChannel reference -> links connector to physical channel

  Sockets (on EthernetPhysicalChannel):
    SocketAddress (hasShortName=True)
      set_networkEndpoint(NetworkEndpoint)
      set_tp() with TpConfiguration (UdpTp or TcpTp)
        UdpTp: set_port(portNumber)
        TcpTp: set_port(portNumber)
    SocketConnectionBundle (hasShortName=True)
      set_serverPortRef(SocketAddress)   — server side
      StaticSocketConnection
        set_clientPortRef(SocketAddress) — client side

  SOME/IP service interface (in shared ArPackage):
    ServiceInterface (hasShortName=True)
      For methods (Client-Server): ClientServerOperation (hasShortName=True)
      For events  (Sender-Receiver): VariableDataPrototype (hasShortName=True)
      For fields  (read/write):     Field (hasShortName=True)

  SOME/IP deployment (in shared ArPackage):
    SomeipServiceInterfaceDeployment (hasShortName=True)
      set_serviceInterfaceRef(ServiceInterface)
      set_serviceInterfaceId(uint16)   — SOME/IP service ID (e.g. 0x1234)
      SomeipMethodDeployment: set_methodId(uint16), set_returnCode(...)
      SomeipEventDeployment:  set_eventId(uint16)

  Service instances (on EcuInstance):
    ProvidedSomeipServiceInstance (hasShortName=True)
      set_serviceInterface(ServiceInterface)
      set_localUnicastAddresses(SocketAddress)
    RequiredSomeipServiceInstance (hasShortName=True)
      set_serviceInterface(ServiceInterface)
      set_localUnicastAddresses(SocketAddress)

  Send signal from SWC over Ethernet/SOME/IP:
    All of Sender-Receiver (SWC to SWC) above, plus:
    ServiceInterface + SomeipServiceInterfaceDeployment
    EthernetCluster + EthernetPhysicalChannel + NetworkEndpoint
    SocketAddress (client + server) + SocketConnectionBundle + StaticSocketConnection
    EcuInstance + EthernetCommunicationController + EthernetCommunicationConnector
    ProvidedSomeipServiceInstance (sender ECU) + RequiredSomeipServiceInstance (receiver ECU)
    ISignalIPdu (with SOME/IP header) + ISignalToIPduMapping
    System + RootSwCompositionPrototype
    SystemMapping -> SenderReceiverToSignalMapping, SwcToEcuMapping

### Parameter interface and calibration
  ParameterInterface is used for calibration data — values that are fixed at
  design/calibration time (not exchanged at runtime like S/R signals).
  Typical use: tuning constants, lookup table values, thresholds.

  Shared declarations (in a shared ArPackage):
    ParameterInterface (hasShortName=True)
      ParameterDataPrototype (hasShortName=True, one per calibration parameter)
        SwDataDefProps -> SwDataDefPropsConditional
          -> set_baseType(SwBaseType)           — for primitive parameters
          -> set_implementationDataType(...)    — for structured/array parameters
        set_initValue(...)                      — default / initial calibration value
                                                  (see Init values section for value containers)

  Calibration provider SWC:
    ParameterSwComponentType (hasShortName=True)
      PPortPrototype  — provides the ParameterInterface
      (no SwcInternalBehavior needed — the component is purely a data container)

  Calibration consumer SWC:
    ApplicationSwComponentType
      RPortPrototype  — requires the ParameterInterface
      SwcInternalBehavior
        RunnableEntity
          ParameterAccess (hasShortName=True)
            set_accessedParameter() -> ref to ParameterDataPrototype
            set_context() -> ref to RPortPrototype
            (use ParameterAccess inside runnable to read the calibration value at runtime)

  Assembly:
    CompositionSwComponentType containing both SWCs as SwComponentPrototype
    AssemblySwConnector connecting provider PPortPrototype to consumer RPortPrototype

  Calibration value sets (optional, for overriding default values per variant):
    CalibrationParameterValueSet (hasShortName=True, in shared ArPackage)
      CalibrationParameterValue (one per parameter)
        set_definitionRef() -> ref to ParameterDataPrototype
        set_value() with appropriate value container (NumericalOrReferenceValue, etc.)

  Note: ParameterDataPrototype supports the same init value shapes as VariableDataPrototype
  (primitive, text, array, record — see Init values section).
  Always call get_class('ParameterDataPrototype') and get_class('ParameterAccess')
  to confirm exact method names before generating code.

### Diagnostic Extract (DEXT)
  DiagnosticContributionSet IS the root node of a DEXT extract.
  There is no separate DiagnosticExtract class — the set itself is the artefact
  consumed by diagnostic tooling (e.g. CANdela, ODX).

  Top-level container (in a shared ArPackage):
    DiagnosticContributionSet (hasShortName=True)
      add_ecuInstance()                — bind to one or more EcuInstance objects
      new_CommonProperties()           — returns DiagnosticCommonProps (shared props)
      new_Element()                    — returns DiagnosticCommonElementRefConditional
                                         use this to add each diagnostic element
                                         (DID, DTC, Routine, Session, etc.) to the set
      new_ServiceTable()               — returns DiagnosticServiceTableRefConditional

  Sessions (in shared ArPackage):
    DiagnosticSession (hasShortName=True)
      Common categories: DEFAULT_SESSION, EXTENDED_DIAGNOSTIC_SESSION, PROGRAMMING_SESSION
      Add to set: DiagnosticContributionSet.new_Element() -> set ref to DiagnosticSession

  Security access (in shared ArPackage):
    DiagnosticSecurityLevel (hasShortName=True)
      set_securityLevelValue(uint8)    — e.g. 0x01 for level 1

  Data Identifiers (DIDs) — UDS service 0x22 ReadDataByIdentifier / 0x2E WriteDataByIdentifier:
    DiagnosticDataIdentifier (hasShortName=True)
      set_id(uint16)                   — DID number e.g. 0xF190
      DiagnosticDataElement (hasShortName=True, one per signal inside the DID)
        SwDataDefProps -> SwDataDefPropsConditional -> set_baseType(SwBaseType)
        set_dataDirection()            — IN (writable) or OUT (readable) or IN_OUT
    Add to set: DiagnosticContributionSet.new_Element() -> set ref to DiagnosticDataIdentifier

  Data mapping — linking a DID data element to a SWC port signal:
    DiagnosticProvidedDataMapping (hasShortName=True, in shared ArPackage)
      use find_creators_of('DiagnosticProvidedDataMapping') to confirm parent class
      set_dataIdentifier() -> ref to DiagnosticDataIdentifier
      set_portPrototype() -> ref to the SWC port that provides/consumes the data

  Trouble Codes (DTCs) — UDS service 0x19 ReadDTCInformation:
    DiagnosticTroubleCodeUds (hasShortName=True)  — NOTE: NOT DiagnosticTroubleCode
      set_udsDtcValue(uint32)          — DTC number e.g. 0x010101
    DiagnosticEvent (hasShortName=True)
      use find_creators_of('DiagnosticEvent') to confirm parent class
    DiagnosticEventToTroubleCodeUdsMapping (hasShortName=True)
      set_diagnosticEvent() -> ref to DiagnosticEvent
      set_troubleCode()     -> ref to DiagnosticTroubleCodeUds
    Add DTC + Event to set via DiagnosticContributionSet.new_Element()

  Fault memory:
    DiagnosticMemoryDestinationPrimary  — primary fault memory (most common)
    DiagnosticMemoryDestinationUserDefined — vendor-defined memory
    DiagnosticMemoryDestinationMirror   — mirror memory
      use find_creators_of('DiagnosticMemoryDestinationPrimary') to confirm parent
    Add to set via DiagnosticContributionSet.new_Element()

  Routines — UDS service 0x31 RoutineControl:
    DiagnosticRoutine (hasShortName=True)
      use find_creators_of('DiagnosticRoutine') to confirm parent class
    DiagnosticRoutineControl (hasShortName=True)
      set_routineControlClass() -> ref to DiagnosticRoutineControlClass
      set_routine()             -> ref to DiagnosticRoutine
    Add to set via DiagnosticContributionSet.new_Element()

  IO control — UDS service 0x2F InputOutputControlByIdentifier:
    DiagnosticIOControl (hasShortName=True)
      use find_creators_of('DiagnosticIOControl') to confirm parent class
    DiagnosticIoControlClass (hasShortName=True)

  Typical DEXT build order:
    1. DiagnosticSession entries
    2. DiagnosticSecurityLevel entries (if needed)
    3. SwBaseType + ImplementationDataType for each DID/DTC data element
    4. DiagnosticDataIdentifier + DiagnosticDataElement entries
    5. DiagnosticTroubleCodeUds + DiagnosticEvent entries
    6. DiagnosticEventToTroubleCodeUdsMapping entries
    7. DiagnosticMemoryDestinationPrimary (or other variant)
    8. DiagnosticRoutine + DiagnosticRoutineControl entries (if needed)
    9. DiagnosticContributionSet -> add_ecuInstance() + new_Element() for each above

  Note: Always call get_class('DiagnosticContributionSet'), get_class('DiagnosticDataIdentifier'),
  get_class('DiagnosticTroubleCodeUds'), and get_class('DiagnosticRoutine') to confirm exact
  method names before generating code. Use find_creators_of() for any element where the
  parent class is uncertain.

### Mode management communication (mode manager SWC <-> mode user SWC)
  Shared declarations (in a shared ArPackage):
    ModeDeclarationGroup + ModeDeclaration (one per mode, e.g. STARTUP, RUN, SHUTDOWN)
    ModeSwitchInterface  — references the ModeDeclarationGroup via set_modeGroup()

  Mode manager SWC (the SWC that controls/switches modes):
    ApplicationSwComponentType
    PPortPrototype  — provides the ModeSwitchInterface
    SwcInternalBehavior
      RunnableEntity (the runnable that decides when to switch mode)
        ModeSwitchPoint — references the PPortPrototype; call set_modeGroup() to link it
          use ModeSwitchPoint to trigger a mode switch at runtime

  Mode user SWC (the SWC that reacts to mode changes):
    ApplicationSwComponentType
    RPortPrototype  — requires the ModeSwitchInterface
    SwcInternalBehavior
      RunnableEntity (triggered when mode changes)
        ModeSwitchEvent — references the RPortPrototype + ModeDeclaration to filter on;
                          set activation to ON-ENTRY, ON-EXIT, or ON-TRANSITION
      RunnableEntity (needs to read the current mode value during execution)
        ModeAccessPoint — references the RPortPrototype; allows reading current mode

  Assembly:
    CompositionSwComponentType containing both SWCs as SwComponentPrototype
    AssemblySwConnector connecting manager PPortPrototype to user RPortPrototype
