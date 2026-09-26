import com.cburch.logisim.proj.Project;
import com.cburch.logisim.proj.ProjectActions;
import java.io.File;

/** Run Logisim's vector evaluator without initializing its Swing entry point. */
final class LogisimHeadlessVector {
  private LogisimHeadlessVector() {}

  public static void main(String[] args) throws Exception {
    if (args.length != 3) {
      System.err.println("usage: LogisimHeadlessVector CIRCUIT VECTOR PROJECT");
      System.exit(2);
    }
    final Project project = ProjectActions.doOpenNoWindow(null, new File(args[2]));
    System.exit(project.doTestVector(args[1], args[0]));
  }
}
