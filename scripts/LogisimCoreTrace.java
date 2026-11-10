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
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

/** Deterministic, settled pre/post-edge observations using pinned Logisim APIs.
 * No VM expectations are passed to this exporter. Labels resolve the existing
 * hierarchy; neither observation pins nor replacement logic are inserted.
 */
final class LogisimCoreTrace {
  private record Offer(long reset, long value, long valid) {}

  private static List<Offer> readOffers(Path path, int limit) throws Exception {
    var lines = Files.readAllLines(path);
    if (lines.size() != limit + 1 || !lines.get(0).equals("edge\tRESET\tINPUT_VALUE\tINPUT_VALID"))
      throw new IllegalArgumentException("missing/extra stimulus rows or wrong columns");
    var offers = new ArrayList<Offer>();
    for (int edge = 1; edge < lines.size(); edge++) {
      var cells = lines.get(edge).split("\t", -1);
      if (cells.length != 4 || !cells[0].equals(Integer.toString(edge))
          || !cells[1].matches("[01]") || !cells[2].matches("[01]{16}")
          || !cells[3].matches("[01]"))
        throw new IllegalArgumentException("invalid stimulus at edge " + edge);
      offers.add(new Offer(Long.parseLong(cells[1]), Long.parseLong(cells[2], 2),
          Long.parseLong(cells[3])));
    }
    return offers;
  }

  private static String known(CircuitState state, String label, int width) {
    var bits = state.getValue(component(state, label).getLocation())
        .toBinaryString().replace(" ", "");
    if (bits.length() != width || !bits.matches("[01]+"))
      throw new IllegalStateException("undefined/wrong-width input readback: " + label + "=" + bits);
    return bits;
  }
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
    var matches = new ArrayList<CircuitState>();
    findChildren(state, label, matches);
    if (matches.size() != 1)
      throw new IllegalArgumentException("ambiguous/missing child label: " + label);
    return matches.get(0);
  }

  private static void findChildren(CircuitState state, String label, List<CircuitState> matches) {
    for (var instance : state.getCircuit().getNonWires()) {
      if (!(instance.getFactory() instanceof SubcircuitFactory factory)) continue;
      if (label.equals(instance.getAttributeSet().getValue(StdAttr.LABEL)))
        matches.add(factory.getSubstate(state, instance));
      else if (factory.getName().startsWith("CPU"))
        findChildren(factory.getSubstate(state, instance), label, matches);
    }
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
    boolean operator = args.length == 5 && args[4].equals("--operator");
    boolean input = args.length == 7 && args[4].equals("--inputs");
    if (args.length != 4 && !operator && !input)
      throw new IllegalArgumentException("usage: LogisimCoreTrace TOP PROJECT PROBES MAX_EDGES [--operator | --inputs STIMULI LEDGER]");
    int limit = Integer.parseInt(args[3]);
    var offers = input ? readOffers(Path.of(args[5]), limit) : List.<Offer>of();
    var project = ProjectActions.doOpenNoWindow(null, new File(args[1]));
    var controller = CircuitState.createRootState(project,
        project.getLogisimFile().getCircuit(args[0]), Thread.currentThread());
    var state = controller;
    if (operator) {
      var cores = controller.getCircuit().getNonWires().stream()
          .filter(c -> c.getFactory() instanceof SubcircuitFactory
              && c.getFactory().getName().equals("TinyCPUMain")).toList();
      if (cores.size() != 1) throw new IllegalArgumentException("operator must contain exactly one core");
      var core = cores.get(0);
      state = ((SubcircuitFactory) core.getFactory()).getSubstate(controller, core);
    }
    // All public core inputs have explicit levels. The standalone core selects
    // internal RAM with USE_EXTERNAL_MEMORY=0. Added inputs fail closed.
    var inputs = new HashMap<>(operator ? Map.of("STEP", 0L, "RESET", 1L, "RUN", 0L)
        : Map.of("CLK", 0L, "RESET", 1L, "ILL_RET", 0L,
        "INTERRUPT_ACCEPT", 0L, "INTERRUPT_TARGET_PC", 0L,
        "EXTERNAL_MEMORY_VALUE", 0L, "EXTERNAL_MEMORY_VALID", 0L,
        "USE_EXTERNAL_MEMORY", 0L, "RAM_WRITE_ENABLE", 0L));
    if (input) {
      inputs.put("INPUT_VALUE", offers.get(0).value());
      inputs.put("INPUT_VALID", offers.get(0).valid());
      for (var spec : Map.of("INPUT_VALUE", 16, "INPUT_VALID", 1).entrySet()) {
        var pin = component(controller, spec.getKey());
        if (pin.getAttributeSet().getValue(StdAttr.WIDTH).getWidth() != spec.getValue())
          throw new IllegalArgumentException("INPUT pin width differs: " + spec.getKey());
      }
    }
    for (var pin : controller.getCircuit().getNonWires()) {
      if (pin.getFactory() instanceof Pin && Circuit.isInput(pin)) {
        String label = pin.getAttributeSet().getValue(StdAttr.LABEL);
        if (!inputs.containsKey(label)) throw new IllegalArgumentException("unspecified input: " + label);
        drive(controller, label, inputs.get(label));
      }
    }
    settle(controller);
    drive(controller, "RESET", 0);
    settle(controller);
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
    var ram = child(child(state, "MEMORY_UNIT"), "MEMORY_INSTANCE");
    try (var ledger = input ? new PrintWriter(Files.newBufferedWriter(Path.of(args[6]))) : null) {
      if (input) ledger.println("edge\tRESET\tINPUT_VALUE\tINPUT_VALID\tINPUT_CONSUME");
      for (int edge = 1; edge <= limit; edge++) {
        drive(controller, operator ? "STEP" : "CLK", 0);
        settle(controller);
        if (input) {
          var offer = offers.get(edge - 1);
          drive(controller, "RESET", offer.reset());
          drive(controller, "INPUT_VALUE", offer.value());
          drive(controller, "INPUT_VALID", offer.valid());
          settle(controller);
        }
        emit(edge, "pre", probes, ram);
        // Independent provider ledger reads the real public pins directly; it
        // does not use the probe list or any VM state/transaction expectations.
        if (input) {
          ledger.println(edge + "\t" + known(state, "RESET", 1) + "\t"
              + known(state, "INPUT_VALUE", 16) + "\t" + known(state, "INPUT_VALID", 1)
              + "\t" + known(state, "INPUT_CONSUME", 1));
          ledger.flush();
          if (ledger.checkError()) throw new IllegalStateException("cannot write consumption ledger");
        }
        boolean halt = Value.TRUE.equals(state.getValue(component(state, "HALTED").getLocation()))
            || Value.TRUE.equals(state.getValue(component(state, "HALTED_WITH_ERROR").getLocation()));
        if (input && offers.get(edge - 1).reset() == 1) halt = false;
        drive(controller, operator ? "STEP" : "CLK", 1);
        settle(controller);
        emit(edge, "post", probes, ram);
        if (halt) {
          if (input && edge != offers.size()) throw new IllegalArgumentException("extra stimulus rows after halt");
          return;
        }
      }
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
