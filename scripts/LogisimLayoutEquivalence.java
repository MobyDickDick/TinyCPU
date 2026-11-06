import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.instance.StdAttr;
import com.cburch.logisim.proj.ProjectActions;
import com.cburch.logisim.std.wiring.Pin;
import java.nio.file.*;
import java.util.*;

/** Differential electrical QA for a schematic redraw, using native Logisim. */
final class LogisimLayoutEquivalence {
  private static Map<String, Component> pins(Circuit circuit, boolean input) {
    var pins = new TreeMap<String, Component>();
    for (var component : circuit.getNonWires()) {
      if (component.getFactory() instanceof Pin && Circuit.isInput(component) == input) {
        String label = component.getAttributeSet().getValue(StdAttr.LABEL);
        if (pins.put(label, component) != null) throw new IllegalArgumentException("duplicate pin " + label);
      }
    }
    return pins;
  }

  private static void drive(CircuitState state, Component pin, long value) {
    Pin.FACTORY.driveInputPin(state.getInstanceState(pin),
        Value.createKnown(pin.getAttributeSet().getValue(StdAttr.WIDTH), value));
    state.markComponentAsDirty(pin);
  }

  private static void settle(CircuitState state) {
    state.getPropagator().propagate();
    if (state.getPropagator().isOscillating()) throw new IllegalStateException("oscillation");
  }

  public static void main(String[] args) throws Exception {
    Path before = Path.of(args[0]), after = Path.of(args[1]);
    int circuits = 0, samples = 0;
    try (var files = Files.walk(before)) {
      for (var file : files.filter(p -> p.toString().endsWith(".circ")).sorted().toList()) {
        Path relative = before.relativize(file);
        var a = ProjectActions.doOpenNoWindow(null, file.toFile());
        var b = ProjectActions.doOpenNoWindow(null, after.resolve(relative).toFile());
        for (var ca : a.getLogisimFile().getCircuits()) {
          var cb = b.getLogisimFile().getCircuit(ca.getName());
          if (cb == null) throw new IllegalStateException("missing circuit " + ca.getName());
          var sa = CircuitState.createRootState(a, ca, Thread.currentThread());
          var sb = CircuitState.createRootState(b, cb, Thread.currentThread());
          var ia = pins(ca, true); var ib = pins(cb, true);
          var oa = pins(ca, false); var ob = pins(cb, false);
          if (!ia.keySet().equals(ib.keySet()) || !oa.keySet().equals(ob.keySet()))
            throw new IllegalStateException("changed interface " + ca.getName());
          for (int step = 0; step < 64; step++) {
            int edge = step / 2;
            for (String label : ia.keySet()) {
              int width = ia.get(label).getAttributeSet().getValue(StdAttr.WIDTH).getWidth();
              if (width != ib.get(label).getAttributeSet().getValue(StdAttr.WIDTH).getWidth())
                throw new IllegalStateException("changed width " + label);
              long value = step < 4 ? 0 : new Random(1701L + 31L * edge + label.hashCode()).nextLong();
              if (label.equals("CLK")) value = step & 1;
              if (label.contains("RESET")) value = step == 1 || step == 2 || step == 48 || step == 49 ? 1 : 0;
              if (width > 1 && edge % 4 == 0)
                value = new long[] {0, 1, 0x7fff, 0x8000, 0xffff}[edge / 4 % 5];
              drive(sa, ia.get(label), value); drive(sb, ib.get(label), value);
            }
            settle(sa); settle(sb);
            for (String label : oa.keySet()) {
              var va = sa.getValue(oa.get(label).getLocation());
              var vb = sb.getValue(ob.get(label).getLocation());
              if (!va.equals(vb) || !vb.isFullyDefined())
                throw new IllegalStateException(relative + ":" + ca.getName() + " step " + step
                    + " " + label + " before=" + va.toBinaryString() + " after=" + vb.toBinaryString());
            }
            samples++;
          }
          circuits++;
          System.out.println(relative + ":" + ca.getName() + " 64 defined, equal samples");
        }
      }
    }
    System.out.println("PASS: " + circuits + " circuits, " + samples + " settled samples");
    System.exit(0);
  }
}
