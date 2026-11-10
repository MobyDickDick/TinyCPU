"""Structural contract for AP 22.1's opt-in INPUT boundary."""
from collections import Counter, defaultdict
import xml.etree.ElementTree as ET
from tiny_cpu_hierarchy import (CORE_UNITS, CircuitBits, attributes, circuit_bit_network, flatten_core,
                                component_ports, wire_path_exists, location)

VARIANTS = {'AccumulatorUnit': 'AccumulatorInputUnit', 'FaultUnit': 'FaultInputUnit'}


def force_terminal(root, circuit_name, instance_label, port, value, width):
    """Disconnect one labelled terminal and force it in a disposable test copy."""
    definitions = {c.get('name'): c for c in root.findall('circuit')}
    circuit = definitions[circuit_name]
    instance = next(c for c in circuit.findall('comp') if attributes(c).get('label') == instance_label)
    terminal = location(next(p for p, *_, label in component_ports(definitions, instance) if label == port))
    branches = [w for w in circuit.findall('wire') if terminal in {w.get('from'), w.get('to')}]
    if len(branches) != 1:
        raise ValueError(f'{instance_label}.{port}: expected one branch, found {len(branches)}')
    circuit.remove(branches[0])
    constant = ET.SubElement(circuit, 'comp', lib='0', name='Constant', loc=terminal)
    ET.SubElement(constant, 'a', name='value', val=hex(value))
    ET.SubElement(constant, 'a', name='width', val=str(width))


def mutate_input(root, mutation):
    if mutation == 'value':
        force_terminal(root, 'AccumulatorInputUnit', 'DATAPATH_INSTANCE', 'DATA_IN', 42, 16)
    elif mutation == 'valid':
        force_terminal(root, 'AccumulatorInputUnit', 'DATAPATH_INSTANCE', 'VALID_IN', 1, 1)
    elif mutation == 'consume':
        main = root.find("circuit[@name='TinyCPUInputMain']")
        pin = next(p for p in main.findall("comp[@name='Pin']") if attributes(p)['label'] == 'INPUT_CONSUME')
        terminal = pin.get('loc')
        branches = [w for w in main.findall('wire') if terminal in w.attrib.values()]
        if len(branches) != 1:
            raise ValueError('consume mutation requires one public output branch')
        main.remove(branches[0])
        constant = ET.SubElement(main, 'comp', lib='0', name='Constant', loc=terminal)
        ET.SubElement(constant, 'a', name='value', val='0x0')
    else:
        raise ValueError(f'unknown INPUT mutation: {mutation}')


def pin_contract(circuit):
    return {attributes(p)['label']: (attributes(p).get('type', 'input'), int(attributes(p).get('width', '1')))
            for p in circuit.findall("comp[@name='Pin']")}


def verify_input_boundary(project):
    definitions = {c.get('name'): c for c in project.findall('circuit')}
    wanted = {'TinyCPUInputMain': ('TinyCPUMain', {'INPUT_VALUE': ('input',16), 'INPUT_VALID': ('input',1), 'INPUT_CONSUME': ('output',1)}),
              'AccumulatorInputUnit': ('AccumulatorUnit', {'INPUT_VALUE': ('input',16), 'INPUT_VALID': ('input',1), 'RESET': ('input',1), 'INPUT_CONSUME': ('output',1)}),
              'FaultInputUnit': ('FaultUnit', {'INPUT_VALID': ('input',1), 'RESET': ('input',1)})}
    for name, (baseline, extra) in wanted.items():
        if name not in definitions or pin_contract(definitions[name]) != {**pin_contract(definitions[baseline]), **extra}:
            raise ValueError(f'{name}: INPUT pin contract differs')
    project = flatten_core(project, transport_only=True, top_name='TinyCPUInputMain')
    definitions = {c.get('name'): c for c in project.findall('circuit')}
    for name in wanted:
        # Check actual terminals, including all old public outputs. Two equal-width
        # output drivers shorted together are also an error, not just width mismatches.
        circuit = definitions[name]
        state = CircuitBits(definitions, circuit, name)
        drivers = defaultdict(list)
        for c in circuit.findall('comp'):
            for p, _, _, outgoing, label in state.ports[id(c)]:
                if outgoing:
                    drivers[state.network.find(p)].append((c.get('name'), attributes(c).get('label'), label))
        if any(len(sources) > 1 for sources in drivers.values()):
            raise ValueError(f'{name}: multiple INPUT boundary net drivers')
        for c in circuit.findall('comp'):
            for p, _, incoming, _, label in state.ports[id(c)]:
                if incoming and not drivers[state.network.find(p)]:
                    raise ValueError(f'{name}: undriven terminal {attributes(c).get("label", c.get("name"))}.{label}')

    main = definitions['TinyCPUInputMain']
    expected_units = {VARIANTS.get(name,name): label for name,label in CORE_UNITS.items()}
    if Counter(c.get('name') for c in main.findall('comp') if c.get('name') != 'Pin') != Counter(expected_units.keys()):
        raise ValueError('TinyCPUInputMain: expected eight functional boxes')
    if any(attributes(c).get('label') != expected_units[c.get('name')] for c in main.findall('comp') if c.get('name') != 'Pin'):
        raise ValueError('TinyCPUInputMain: functional labels differ')

    def network(name):
        circuit = definitions[name]
        state, aliases = circuit_bit_network(definitions, circuit)
        components = {attributes(c).get('label'): c for c in circuit.findall('comp') if attributes(c).get('label')}
        def terminal(label, port=None):
            c = components[label]
            ports = component_ports(definitions, c)
            return next((p,w) for p,w,*_,name in ports if port is None or port == name)
        def same(a,b):
            p,w = terminal(*a);q,v = terminal(*b)
            return w == v and all(aliases.find(x) == aliases.find(y) for x,y in zip(state.vector(p,w),state.vector(q,v)))
        def require(a,b):
            if not same(a,b):
                raise ValueError(f'{name}: INPUT path {a} -> {b} disconnected')
        def decode(label, port, bit=34):
            p,w = terminal(label,port);control,bits = terminal('CONTROL')
            if w != 1 or aliases.find(state.vector(p,w)[0]) != aliases.find(state.vector(control,bits)[bit]):
                raise ValueError(f'{name}: INPUT decode is not CONTROL.{bit}')
        if name == 'AccumulatorInputUnit':
            # Multiplexer captions may disappear on a native GUI save. Follow
            # the real data path instead of requiring those optional labels.
            for label, sink, port in [('INPUT_DATA_SELECT', 'DATAPATH_INSTANCE', 'DATA_IN'),
                                      ('INPUT_CANONICAL_VALUE', 'INPUT_DATA_SELECT', '1')]:
                target, width = terminal(sink, port)
                matches = [mux for mux in circuit.findall("comp[@name='Multiplexer']")
                           if attributes(mux).get('width') == '16'
                           and state.network.find(component_ports(definitions, mux)[0][0])
                           == state.network.find(target)]
                if len(matches) != 1:
                    raise ValueError(f'{name}: missing or ambiguous {label} data path')
                components[label] = matches[0]
        return components,require,decode

    c,require,_ = network('TinyCPUInputMain')
    for a,b in [(('INPUT_VALUE',),('ACCUMULATOR_UNIT','INPUT_VALUE')),
                (('INPUT_VALID',),('ACCUMULATOR_UNIT','INPUT_VALID')),
                (('INPUT_VALID',),('FAULT_UNIT','INPUT_VALID')),
                (('RESET',),('ACCUMULATOR_UNIT','RESET')),
                (('RESET',),('FAULT_UNIT','RESET')),
                (('INPUT_CONSUME',),('ACCUMULATOR_UNIT','INPUT_CONSUME'))]:
        require(a,b)
    c,require,decode = network('AccumulatorInputUnit')
    for label in ('INPUT_DATA_SELECT', 'INPUT_CANONICAL_VALUE'):
        if c[label].get('name') != 'Multiplexer' or attributes(c[label]).get('width') != '16':
            raise ValueError('AccumulatorInputUnit: INPUT data selection differs')
    zero_terminal = next(p for p, *_, port in component_ports(definitions, c['INPUT_CANONICAL_VALUE']) if port == '0')
    zero_sources = [attributes(source) for source in definitions['AccumulatorInputUnit'].findall("comp[@name='Constant']")
                    if wire_path_exists(definitions['AccumulatorInputUnit'], source.get('loc'), location(zero_terminal))]
    if len(zero_sources) != 1 or int(zero_sources[0].get('value', '0x1'), 0) != 0 or zero_sources[0].get('width') != '16':
        raise ValueError('AccumulatorInputUnit: INPUT invalid data must be a defined 16-bit zero')
    for a,b in [(('INPUT_DATA_SELECT','output'),('DATAPATH_INSTANCE','DATA_IN')),
                (('RESULT_VALUE',),('INPUT_DATA_SELECT','0')),
                (('INPUT_CANONICAL_VALUE','output'),('INPUT_DATA_SELECT','1')),
                (('INPUT_VALUE',),('INPUT_CANONICAL_VALUE','1')),
                (('INPUT_VALID',),('INPUT_CANONICAL_VALUE','select')),
                (('RESET',),('INPUT_CONSUME_REQUEST','1')),
                (('INPUT_CONSUME',),('INPUT_CONSUME_REQUEST','output'))]:
        require(a,b)
    decode('INPUT_DATA_SELECT','select');decode('INPUT_CONSUME_REQUEST','0')
    if c['INPUT_CONSUME_REQUEST'].get('name') != 'AND Gate' or attributes(c['INPUT_CONSUME_REQUEST']).get('negate1') != 'true':
        raise ValueError('AccumulatorInputUnit: INPUT reset guard differs')
    for a,b in [(('RESET',),('G1','1')),
                (('G1','output'),('G2','1')),
                (('G2','output'),('DATAPATH_INSTANCE','ACC_LOAD'))]:
        require(a,b)
    decode('G1','0');decode('G2','0',41)
    if c['G1'].get('name') != 'NAND Gate' or c['G2'].get('name') != 'AND Gate':
        raise ValueError('AccumulatorInputUnit: INPUT load reset guard differs')
    c,require,decode = network('FaultInputUnit')
    require(('INPUT_VALID',),('INPUT_FAILED','1'))
    require(('RESET',),('INPUT_FAILED','2'))
    require(('INPUT_FAILED','output'),('ERROR_FLAGS','SET_INPUT'))
    decode('INPUT_FAILED','0')
    if (c['INPUT_FAILED'].get('name') != 'AND Gate'
            or attributes(c['INPUT_FAILED']).get('negate1') != 'true'
            or attributes(c['INPUT_FAILED']).get('negate2') != 'true'
            or attributes(c['INPUT_FAILED']).get('inputs') != '3'):
        raise ValueError('FaultInputUnit: INPUT failure guard differs')
