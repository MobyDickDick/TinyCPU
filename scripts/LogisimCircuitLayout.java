import com.cburch.logisim.proj.ProjectActions;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.comp.ComponentDrawContext;
import com.cburch.logisim.instance.StdAttr;
import java.io.File;
import java.nio.file.*;
import java.awt.Color;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import javax.imageio.ImageIO;

/** Native terminal geometry and drawings, without saving a Logisim project. */
final class LogisimCircuitLayout {
  public static void main(String[] args) throws Exception {
    Path output = Path.of(args[0]);
    Files.createDirectories(output);
    try (var manifest = Files.newBufferedWriter(output.resolve("contacts.tsv"))) {
      for (int i = 1; i < args.length; i++) {
        var project = ProjectActions.doOpenNoWindow(null, new File(args[i]));
        String file = Path.of(args[i]).getFileName().toString();
        for (var circuit : project.getLogisimFile().getCircuits()) {
          String name = circuit.getName();
          for (var component : circuit.getNonWires()) {
            var loc = component.getLocation();
            var bounds = component.getBounds();
            String label = component.getAttributeSet().containsAttribute(StdAttr.LABEL)
                ? component.getAttributeSet().getValue(StdAttr.LABEL) : "";
            String prefix = file + "\t" + name + "\t" + loc + "\t"
                + component.getFactory().getName();
            manifest.write("C\t" + prefix + "\t" + bounds.getX() + "\t"
                + bounds.getY() + "\t" + bounds.getWidth() + "\t"
                + bounds.getHeight() + "\t" + label + "\n");
            for (int n = 0; n < component.getEnds().size(); n++) {
              var end = component.getEnds().get(n);
              manifest.write("P\t" + prefix + "\t" + n + "\t" + end.getLocation()
                  + "\t" + end.getWidth().getWidth() + "\t" + end.isInput()
                  + "\t" + end.isOutput() + "\n");
            }
          }
          var state = CircuitState.createRootState(project, circuit, Thread.currentThread());
          var temporary = new BufferedImage(1, 1, BufferedImage.TYPE_INT_RGB).createGraphics();
          var bounds = circuit.getBounds(temporary);
          temporary.dispose();
          var image = new BufferedImage(bounds.getWidth() + 80, bounds.getHeight() + 80,
              BufferedImage.TYPE_INT_RGB);
          var graphics = image.createGraphics();
          graphics.setColor(Color.WHITE);
          graphics.fillRect(0, 0, image.getWidth(), image.getHeight());
          graphics.translate(40 - bounds.getX(), 40 - bounds.getY());
          graphics.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
          var context = new ComponentDrawContext(null, circuit, state, graphics, graphics, false);
          context.setShowState(false);
          context.setShowColor(true);
          circuit.draw(context, null);
          graphics.dispose();
          ImageIO.write(image, "png", output.resolve(file + "--" + name + ".png").toFile());
          System.out.println(file + ":" + name + " " + image.getWidth() + "x" + image.getHeight());
        }
      }
    }
    System.exit(0);
  }
}
