import importlib.util,copy,sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tiny_cpu_input_boundary import verify_input_boundary, pin_contract
from tiny_cpu_hierarchy import attributes,flatten_core
from tiny_cpu_core_trace import expected_trace,CoreMismatch,SIGNALS
from tiny_cpu_assembler import assemble
spec=importlib.util.spec_from_file_location('input_boundary_driver',ROOT/'scripts/test-logisim-input-boundary.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)

class InputBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.project=ET.parse(ROOT/'hardware/logisim/TinyCPU.circ').getroot()

    def test_additional_boundary_keeps_the_old_interface_and_eight_boxes(self):
        verify_input_boundary(self.project)
        self.assertEqual(len(pin_contract(self.project.find("circuit[@name='TinyCPUMain']"))),33)
        self.assertEqual(len(pin_contract(self.project.find("circuit[@name='TinyCPUInputMain']"))),36)

    def test_missing_or_wrong_width_input_is_rejected(self):
        pin=next(p for p in self.project.find("circuit[@name='TinyCPUInputMain']").findall("comp[@name='Pin']") if attributes(p)['label']=='INPUT_VALUE')
        pin.find("a[@name='width']").set('val','12')
        with self.assertRaisesRegex(ValueError,'pin contract'):
            verify_input_boundary(self.project)

    def test_gui_saved_multiplexer_captions_are_optional(self):
        unit = self.project.find("circuit[@name='AccumulatorInputUnit']")
        for mux in unit.findall("comp[@name='Multiplexer']"):
            for label in mux.findall("a[@name='label']"):
                mux.remove(label)
        verify_input_boundary(self.project)

    def test_valid_transaction_cannot_set_the_input_error(self):
        gate=next(c for c in self.project.find("circuit[@name='FaultInputUnit']").findall('comp') if attributes(c).get('label')=='INPUT_FAILED')
        gate.remove(gate.find("a[@name='negate1']"))
        with self.assertRaisesRegex(ValueError,'guard differs|undriven'):
            verify_input_boundary(self.project)

    def test_reset_consumption_and_same_width_driver_short_are_rejected(self):
        main=self.project.find("circuit[@name='TinyCPUInputMain']")
        pins={attributes(p)['label']:p.get('loc') for p in main.findall("comp[@name='Pin']")}
        ET.SubElement(main,'wire',{'from':pins['INPUT_CONSUME'],'to':pins['HALTED_WITH_ERROR']})
        with self.assertRaisesRegex(ValueError,'multiple.*drivers'):
            verify_input_boundary(self.project)

    def test_disconnected_new_input_cannot_pass_the_contract(self):
        main=self.project.find("circuit[@name='TinyCPUInputMain']")
        pin=next(p for p in main.findall("comp[@name='Pin']") if attributes(p)['label']=='INPUT_VALUE')
        wire=next(w for w in main.findall('wire') if pin.get('loc') in w.attrib.values());main.remove(wire)
        with self.assertRaisesRegex(ValueError,'undriven|disconnected'):
            verify_input_boundary(self.project)

    def test_gui_saved_access_gate_gets_an_analysis_name_from_its_connection(self):
        c=self.project.find("circuit[@name='AddressAccess']")
        gate=c.find("comp[@name='NOR Gate']")
        for label in gate.findall("a[@name='label']"):gate.remove(label)
        before=ET.tostring(self.project)
        flat=flatten_core(self.project)
        self.assertEqual(len([g for g in flat.find("circuit[@name='TinyCPUMain']").findall("comp[@name='NOR Gate']") if attributes(g).get('label')=='ACCESS_VALID']),1)
        self.assertEqual(before,ET.tostring(self.project))
        pin=next(p for p in c.findall("comp[@name='Pin']") if attributes(p)['label']=='ACCESS_VALID')
        for w in list(c.findall('wire')):
            if pin.get('loc') in w.attrib.values():c.remove(w)
        flat=flatten_core(self.project)
        self.assertFalse(any(attributes(g).get('label')=='ACCESS_VALID' for g in flat.find("circuit[@name='TinyCPUMain']").findall("comp[@name='NOR Gate']")))

    def test_reference_queue_is_copied_and_default_remains_unavailable(self):
        program=assemble('INPUT()\nHALT()\n');values=[-1]
        rows=expected_trace(program,inputs=values)
        self.assertEqual(values,[-1]);self.assertEqual((rows[1]['ACC'],rows[1]['ACC_VALID'],rows[1]['ERROR_INPUT']),(65535,1,0))
        rows=expected_trace(program)
        self.assertEqual((rows[1]['ACC'],rows[1]['ACC_VALID'],rows[1]['ERROR_INPUT']),(0,0,1))

    def test_boundary_comparator_rejects_undefined_consumption_and_missing_samples(self):
        program=assemble('INPUT()\nHALT()\n');expected=expected_trace(program)
        header=['edge','phase',*SIGNALS,'INPUT_CONSUME','MEMORY']
        raw='\t'.join(header)+'\n'+'\t'.join(['1','pre',*['0'*w for w,_ in SIGNALS.values()],'E','-'])+'\n'
        with self.assertRaisesRegex(CoreMismatch,'INPUT_CONSUME'):
            driver.compare_boundary(raw,expected,program)
        with self.assertRaisesRegex(CoreMismatch,'sample'):
            driver.compare_boundary('\t'.join(header)+'\n',expected,program)

if __name__=='__main__':unittest.main()
