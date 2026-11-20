import javax.tools.*;
import java.io.File;
import java.lang.reflect.Method;
import java.net.*;
import java.nio.file.*;
import java.util.*;

/**
 * Generic variant runner for JVM games.
 *   java Probe <game.jar> <MetricClass> <variantDir|-> ...
 * Each variantDir holds patched .java files (any package path). They are compiled against the
 * game jar and run in an isolated class loader, so every variant gets a fresh copy of the game.
 * "-" means the unpatched baseline. Prints one JSON line per variant.
 * -Dprobe.sourcepath=<dirs> supplies compile-time-only sources the jar lacks (e.g. annotation types).
 */
public class Probe{
    public static void main(String[] args) throws Exception{
        Path jar = Paths.get(args[0]).toAbsolutePath();
        URL self = Paths.get(Probe.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toUri().toURL();
        JavaCompiler javac = ToolProvider.getSystemJavaCompiler();

        for(int i = 2; i < args.length; i++){
            String name = args[i];
            try{
                List<URL> path = new ArrayList<>();
                if(!name.equals("-")) path.add(compile(javac, Paths.get(name), jar));
                path.add(jar.toUri().toURL());
                path.add(self);
                try(URLClassLoader loader = new URLClassLoader(path.toArray(new URL[0]), ClassLoader.getPlatformClassLoader())){
                    Method m = loader.loadClass(args[1]).getMethod("measure");
                    System.out.println("{\"variant\":\"" + name + "\",\"metrics\":" + m.invoke(null) + "}");
                }
            }catch(Throwable t){
                Throwable c = t.getCause() != null ? t.getCause() : t;
                System.out.println("{\"variant\":\"" + name + "\",\"error\":\"" + String.valueOf(c).replace("\"", "'").replace("\n", " ") + "\"}");
            }
        }
    }

    static URL compile(JavaCompiler javac, Path dir, Path jar) throws Exception{
        Path out = dir.resolve("classes");
        Files.createDirectories(out);
        List<File> srcs = new ArrayList<>();
        try(var walk = Files.walk(dir)){ walk.filter(p -> p.toString().endsWith(".java")).forEach(p -> srcs.add(p.toFile())); }
        try(StandardJavaFileManager fm = javac.getStandardFileManager(null, null, null)){
            var diag = new DiagnosticCollector<JavaFileObject>();
            boolean ok = javac.getTask(null, fm, diag, List.of("-nowarn", "-proc:none", "-implicit:none", "-cp", jar.toString(),
                    "-sourcepath", System.getProperty("probe.sourcepath", ""), "-d", out.toString()),
                null, fm.getJavaFileObjectsFromFiles(srcs)).call();
            if(!ok) throw new IllegalStateException("compile failed: " + diag.getDiagnostics().get(0).getMessage(null));
        }
        return out.toUri().toURL();
    }
}
