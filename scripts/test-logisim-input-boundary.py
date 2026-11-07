#!/usr/bin/env python3
"""AP 22.1 step 2: electrical acceptance of the additional static INPUT boundary.

Only artifact copies bind the two new input pins to fixed constants. Production
pins stay public. Per-edge stimuli and full input-matrix integration are step 3/4.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from tiny_cpu_assembler import assemble, encode_program
from tiny_cpu_core_trace import CoreMismatch, SIGNALS, compare_trace, expected_trace
from tiny_cpu_hierarchy import attributes, component_ports, location
from tiny_cpu_logisim import LogisimError, _inject_rom, resolve_jar
from tiny_cpu_profiles import load_profile


def bind_static_input(root, value, valid):
    main = root.find("circuit[@name='TinyCPUInputMain']")
    for pin in main.findall("comp[@name='Pin']"):
        a = attributes(pin)
        if a['label'] in {'INPUT_VALUE', 'INPUT_VALID'}:
            pin.set('name', 'Constant')
            for child in list(pin):
                pin.remove(child)
            ET.SubElement(pin, 'a', name='width', val=a.get('width', '1'))
            ET.SubElement(pin, 'a', name='value', val=hex(value if a['label'] == 'INPUT_VALUE' else valid))


def compare_boundary(text, expected, program):
    lines = text.splitlines()
    header = ['edge', 'phase', *SIGNALS, 'INPUT_CONSUME', 'MEMORY']
    if not lines or lines[0].split('\t') != header:
        raise CoreMismatch(0, 'schema', 'columns', header, lines[0] if lines else '<missing>')
    projected = ['\t'.join(['edge', 'phase', *SIGNALS, 'MEMORY'])]
    for index, line in enumerate(lines[1:]):
        cells = line.split('\t')
        if len(cells) != len(header):
            raise CoreMismatch(index // 2 + 1, 'schema', 'columns', len(header), len(cells))
        raw = dict(zip(header, cells))
        projected_row = '\t'.join(raw[name] for name in ['edge', 'phase', *SIGNALS, 'MEMORY'])
        # Compare in sample order: a later consume failure must not hide an
        # earlier bad accumulator/RAM state.
        if index < len(expected):
            compare_trace(projected[0] + '\n' + projected_row + '\n', [expected[index]])
        if raw['INPUT_CONSUME'] not in {'0', '1'}:
            raise CoreMismatch(index // 2 + 1, raw['phase'], 'INPUT_CONSUME', '1 defined bit', raw['INPUT_CONSUME'])
        # Fixed independent transaction rule, not read from VM consumption.
        if index < len(expected) and expected[index]['phase'] == 'pre':
            pc = expected[index]['PC']
            wanted = int(program.instructions[pc].mnemonic == 'INPUT')
            if int(raw['INPUT_CONSUME']) != wanted:
                raise CoreMismatch(expected[index]['edge'], 'pre', 'INPUT_CONSUME', wanted, int(raw['INPUT_CONSUME']))
        projected.append(projected_row)
    compare_trace('\n'.join(projected) + '\n', expected)


def force_terminal(root, circuit_name, instance_label, port, value, width):
    definitions = {c.get('name'): c for c in root.findall('circuit')}
    circuit = definitions[circuit_name]
    instance = next(c for c in circuit.findall('comp') if attributes(c).get('label') == instance_label)
    terminal = location(next(p for p, *_, label in component_ports(definitions, instance) if label == port))
    branches = [w for w in circuit.findall('wire') if terminal in {w.get('from'), w.get('to')}]
    if len(branches) != 1:
        raise LogisimError(f'{instance_label}.{port}: expected one branch, found {len(branches)}')
    circuit.remove(branches[0])
    constant = ET.SubElement(circuit, 'comp', lib='0', name='Constant', loc=terminal)
    ET.SubElement(constant, 'a', name='value', val=hex(value))
    ET.SubElement(constant, 'a', name='width', val=str(width))


def run_case(source, output, jar, java, code, value, valid, mutation=None):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'diagnostic.json').unlink(missing_ok=True)
    profile = load_profile()
    program = assemble(code, profile)
    signed = value if value < 32768 else value - 65536
    expected = expected_trace(program, inputs=[signed] * 64 if valid else [])
    tree = ET.parse(source)
    root = tree.getroot()
    _inject_rom(root, source, tuple(encode_program(program)))
    bind_static_input(root, value, valid)
    if mutation == 'value':
        force_terminal(root, 'AccumulatorInputUnit', 'DATAPATH_INSTANCE', 'DATA_IN', 42, 16)
    elif mutation == 'valid':
        force_terminal(root, 'AccumulatorInputUnit', 'DATAPATH_INSTANCE', 'VALID_IN', 1, 1)
    elif mutation == 'consume':
        main = root.find("circuit[@name='TinyCPUInputMain']")
        pin = next(p for p in main.findall("comp[@name='Pin']")
                   if attributes(p)['label'] == 'INPUT_CONSUME')
        terminal = pin.get('loc')
        branches = [w for w in main.findall('wire') if terminal in w.attrib.values()]
        if len(branches) != 1:
            raise LogisimError('consume mutation requires one public output branch')
        main.remove(branches[0])
        constant = ET.SubElement(main, 'comp', lib='0', name='Constant', loc=terminal)
        ET.SubElement(constant, 'a', name='value', val='0x0')
    project = output / 'TinyCPU.circ'
    tree.write(project, encoding='utf-8', xml_declaration=True)
    probes = output / 'probes.tsv'
    probes.write_text(''.join(f'{name}\t{path}\n' for name, (_, path) in SIGNALS.items()) + 'INPUT_CONSUME\tINPUT_CONSUME\n', encoding='utf-8')
    (output / 'program.tcpu').write_text(code, encoding='utf-8')
    (output / 'expected.json').write_text(json.dumps(expected, indent=2) + '\n')
    (output / 'inputs.json').write_text(json.dumps({'mode': 'static-artifact-binding', 'value': value, 'valid': valid}, indent=2) + '\n')
    command = [java, '-Djava.awt.headless=true', '-cp', str(jar.resolve()), str(ROOT / 'scripts/LogisimCoreTrace.java'), 'TinyCPUInputMain', str(project.resolve()), str(probes.resolve()), str(len(expected) // 2 + 1)]
    (output / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    with (output / 'trace.tsv').open('wb') as stdout, (output / 'stderr.txt').open('wb') as stderr:
        result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=30, check=False)
    if result.returncode:
        raise LogisimError(f'input boundary exporter failed ({result.returncode}); evidence: {output}')
    try:
        compare_boundary((output / 'trace.tsv').read_text(), expected, program)
    except CoreMismatch as exc:
        (output / 'diagnostic.json').write_text(json.dumps(vars(exc), indent=2) + '\n')
        raise
    # Independent fixed expectations on the first INPUT result.
    pre = next((i for i, r in enumerate(expected) if r['phase'] == 'pre' and program.instructions[r['PC']].mnemonic == 'INPUT'), None)
    if pre is not None:
        post = expected[pre + 1]
        assert (post['ACC'], post['ACC_VALID'], post['ERROR_INPUT']) == (value if valid else 0, valid, 0 if valid else 1)
    return len(expected) // 2


def check_reset(source, output, jar, java):
    # Independent truth table, including RESET=1 while INPUT decode remains 1.
    project = ET.parse(source).getroot()
    circuit = project.find("circuit[@name='AccumulatorInputUnit']")
    inputs = [attributes(p) for p in circuit.findall("comp[@name='Pin']") if attributes(p).get('type') != 'output']
    header = [a['label'] + (f"[{a['width']}]" if int(a.get('width', '1')) > 1 else '') for a in inputs]
    rows = [' '.join([*header, 'INPUT_CONSUME'])]
    for decoded, reset, clk, valid in [(0,0,0,1), (1,0,0,1), (1,0,1,1), (1,1,0,1), (1,1,1,1), (1,0,0,0), (0,0,1,0)]:
        values = {'CONTROL': (decoded << 34), 'RESET': reset, 'CLK': clk, 'INPUT_VALUE': 23, 'INPUT_VALID': valid}
        cells = [format(values.get(a['label'], 0), f"0{a.get('width', '1')}b") for a in inputs]
        rows.append(' '.join([*cells, str(decoded and not reset and 1 or 0)]))
    vector = output / 'reset.txt'
    vector.write_text('\n'.join(rows) + '\n')
    command = [java, '-Djava.awt.headless=true', '-cp', str(jar.resolve()), str(ROOT / 'scripts/LogisimHeadlessVector.java'), 'AccumulatorInputUnit', str(vector.resolve()), str(source.resolve())]
    (output / 'reset-command.json').write_text(json.dumps(command, indent=2) + '\n')
    with (output / 'reset-log.txt').open('wb') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=30)
    if result.returncode:
        raise LogisimError(f'INPUT_CONSUME reset truth table failed; evidence: {output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/input-boundary')
    parser.add_argument('--java', default=os.environ.get('JAVA', 'java'))
    parser.add_argument('--jar', type=Path, default=Path(os.environ['LOGISIM_JAR']) if os.environ.get('LOGISIM_JAR') else None)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    proof = args.output / 'proof.json'
    proof.unlink(missing_ok=True)
    source = ROOT / 'hardware/logisim/TinyCPU.circ'
    originals = {p: p.read_bytes() for p in source.parent.rglob('*.circ')}
    jar = resolve_jar(args.jar)
    cases = {f'value-{value:04x}': ('INPUT()\nPRINT()\nHALT()\n', value, 1) for value in [0,65535,32768,32767]}
    cases.update({
        'unavailable': ('LOAD_CONST(7)\nINPUT()\nHALT()\n', 0xffff, 0),
        'invalid-print-clear': ('INPUT()\nPRINT()\nCLEAR_ERROR()\nHALT()\n', 23, 0),
        'consecutive': ('INPUT()\nINPUT()\nPRINT()\nHALT()\n', 17, 1),
        'store-read': ('INPUT()\nSTORE_ADDRESS(20)\nLOAD_CONST(0)\nLOAD_ADDRESS(20)\nPRINT()\nHALT()\n', 0xffff, 1),
        'skip-input': ('LOAD_CONST(7)\nJUMP_ADDRESS(3)\nINPUT()\nPRINT()\nHALT()\n', 42, 1),
        'sticky-success': ('PRINT()\nINPUT()\nPRINT()\nCLEAR_ERROR()\nHALT()\n', 23, 1),
    })
    results = {}
    try:
        for name, (code, value, valid) in cases.items():
            results[name] = run_case(source, args.output / name, jar, args.java, code, value, valid)
            print(f'PASS {name}', flush=True)
        check_reset(source, args.output, jar, args.java)
        mutations = {}
        for name, value, valid, wanted in [('value',23,1,(1,'post','ACC',23,42)), ('valid',23,0,(1,'post','ACC_VALID',0,1)), ('consume',23,1,(1,'pre','INPUT_CONSUME',1,0))]:
            try:
                run_case(source, args.output / f'mutation-{name}', jar, args.java, 'INPUT()\nHALT()\n', value, valid, name)
            except CoreMismatch as exc:
                assert (exc.edge, exc.phase, exc.signal, exc.expected, exc.actual) == wanted, str(exc)
                mutations[name] = vars(exc)
                print(f'REJECT mutation-{name}: {exc}', flush=True)
            else:
                raise LogisimError(f'input mutation {name} was accepted')
    finally:
        if any(p.read_bytes() != data for p, data in originals.items()):
            raise LogisimError('input tests modified production circuits')
    proof.write_text(json.dumps({'scope': 'AP22.1 step2 static boundary; dynamic stimuli not accepted yet', 'cases': results, 'reset_rows': 7, 'mutations': mutations, 'source_circuits_unchanged': True, 'source_sha256': hashlib.sha256(originals[source]).hexdigest()}, indent=2) + '\n')
    print('INPUT boundary passed: 10 core/VM comparisons, reset truth table, three rejected electrical mutations')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
