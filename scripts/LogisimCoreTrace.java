import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.circuit.SubcircuitFactory;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.instance.StdAttr;
import com.cburch.logisim.proj.ProjectActions;
import com.cburch.logisim.std.memory.Ram;
import com.cburch.logisim.std.wiring.Pin;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Deterministic, settled pre/post-edge observations using pinned Logisim APIs.
 * No VM expectations are passed to this exporter. Labels resolve the existing
 * hierarchy; neither observation pins nor replacement logic are inserted.
 */
final class LogisimCoreTrace {
  private record Probe(String name, CircuitState state, Component component) {
    Value value() { return state.getValue(component.getLocation()); }
  }

  private static Component component(CircuitState state, String label) {
    var matches = state.getCircuit().getNonWires().stream()
        .filter(c -> label.equals(c.getAttributeSet().getValue(StdAttr.LABEL))).toList();
    if (matches.size() != 1) throw new IllegalArgumentException("ambiguous/missing label: " + label);
    return matches.get(0);
  }

  private static CircuitState child(CircuitState state, String label) {
    var instance = component(state, label);
    return ((SubcircuitFactory) instance.getFactory()).getSubstate(state, instance);
  }

  private static void drive(CircuitState state, String label, long value) {
    var pin = component(state, label);
    if (!(pin.getFactory() instanceof Pin) || !Circuit.isInput(pin))
      throw new IllegalArgumentException("not an input pin: " + label);
    Pin.FACTORY.driveInputPin(state.getInstanceState(pin),
        Value.createKnown(pin.getAttributeSet().getValue(StdAttr.WIDTH), value));
    state.markComponentAsDirty(pin);
  }

  private static void settle(CircuitState state) {
    state.getPropagator().propagate();
    if (state.getPropagator().isOscillating()) throw new IllegalStateException("oscillation");
  }

  private static String memory(CircuitState state) {
    var data = component(state, "DATA_RAM");
    var valid = component(state, "VALID_RAM");
    var values = ((Ram) data.getFactory()).getContents(state.getInstanceState(data));
    var validity = ((Ram) valid.getFactory()).getContents(state.getInstanceState(valid));
    if (values.getLastOffset() != validity.getLastOffset())
      throw new IllegalStateException("RAM address widths differ");
    var words = new ArrayList<String>();
    for (long address = 0; address <= values.getLastOffset(); address++) {
      long value = values.get(address), bit = validity.get(address);
      if (value != 0 || bit != 0) words.add(address + ":" + value + ":" + bit);
    }
    return words.isEmpty() ? "-" : String.join(",", words);
  }

  private static void emit(int edge, String phase, List<Probe> probes, CircuitState ram) {
    var row = new ArrayList<String>();
    row.add(Integer.toString(edge));
    row.add(phase);
    for (var probe : probes) row.add(probe.value().toBinaryString().replace(" ", ""));
    row.add(memory(ram));
    System.out.println(String.join("\t", row));
    System.out.flush();
  }

  private static void run(String[] args) throws Exception {
    if (args.length != 4)
      throw new IllegalArgumentException("usage: LogisimCoreTrace TOP PROJECT PROBES MAX_EDGES");
    var project = ProjectActions.doOpenNoWindow(null, new File(args[1]));
    var state = CircuitState.createRootState(project,
        project.getLogisimFile().getCircuit(args[0]), Thread.currentThread());
    // All public core inputs have explicit levels. The standalone core selects
    // internal RAM with USE_EXTERNAL_MEMORY=0. Added inputs fail closed.
    var inputs = Map.of("CLK", 0L, "RESET", 1L, "ILL_RET", 0L,
        "INTERRUPT_ACCEPT", 0L, "INTERRUPT_TARGET_PC", 0L,
        "EXTERNAL_MEMORY_VALUE", 0L, "EXTERNAL_MEMORY_VALID", 0L,
        "USE_EXTERNAL_MEMORY", 0L, "RAM_WRITE_ENABLE", 0L);
    for (var pin : state.getCircuit().getNonWires()) {
      if (pin.getFactory() instanceof Pin && Circuit.isInput(pin)) {
        String label = pin.getAttributeSet().getValue(StdAttr.LABEL);
        if (!inputs.containsKey(label)) throw new IllegalArgumentException("unspecified input: " + label);
        drive(state, label, inputs.get(label));
      }
    }
    settle(state);
    drive(state, "RESET", 0);
    settle(state);
    var probes = new ArrayList<Probe>();
    var header = new ArrayList<String>(List.of("edge", "phase"));
    for (String line : Files.readAllLines(Path.of(args[2]))) {
      String[] fields = line.split("\t");
      var owner = state;
      String[] path = fields[1].split("/");
      for (int i = 0; i < path.length - 1; i++) owner = child(owner, path[i]);
      probes.add(new Probe(fields[0], owner, component(owner, path[path.length - 1])));
      header.add(fields[0]);
    }
    header.add("MEMORY");
    System.out.println(String.join("\t", header));
    var ram = child(state, "MEMORY_INSTANCE");
    for (int edge = 1; edge <= Integer.parseInt(args[3]); edge++) {
      drive(state, "CLK", 0);
      settle(state);
      emit(edge, "pre", probes, ram);
      boolean halt = Value.TRUE.equals(state.getValue(component(state, "HALTED").getLocation()))
          || Value.TRUE.equals(state.getValue(component(state, "HALTED_WITH_ERROR").getLocation()));
      drive(state, "CLK", 1);
      settle(state);
      emit(edge, "post", probes, ram);
      if (halt) return;
    }
    throw new IllegalStateException("no terminal instruction within edge limit");
  }

  public static void main(String[] args) {
    try {
      run(args);
      System.exit(0);
    } catch (Throwable error) {
      error.printStackTrace();
      System.exit(1);
    }
  }
}
