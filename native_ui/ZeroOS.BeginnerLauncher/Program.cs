using System.Diagnostics;
using System.Windows.Forms;

var repoRoot = ResolveRepoRoot();
var exeName = Path.GetFileNameWithoutExtension(Environment.ProcessPath ?? "ZeroOS.BeginnerLauncher").ToLowerInvariant();

return exeName switch
{
    var name when name.Contains("quickstart") => RunQuickStart(repoRoot),
    var name when name.Contains("native shell") => OpenNativeShell(repoRoot),
    _ => OpenZeroOs(repoRoot),
};

static int RunQuickStart(string repoRoot)
{
    var launcher = Path.Combine(repoRoot, "zero_os_launcher.ps1");
    if (!File.Exists(launcher))
    {
        ShowError("zero_os_launcher.ps1 is missing.");
        return 1;
    }

    var firstRun = RunHidden(
        "powershell",
        $"-NoProfile -ExecutionPolicy Bypass -File \"{launcher}\" first-run",
        repoRoot);

    if (firstRun.ExitCode != 0)
    {
        ShowError("First-run failed. Review the terminal output and try again.");
        return firstRun.ExitCode;
    }

    return OpenZeroOs(repoRoot);
}

static int OpenZeroOs(string repoRoot)
{
    var ui = Path.Combine(repoRoot, "zero_os_ui.py");
    if (!File.Exists(ui))
    {
        ShowError("zero_os_ui.py is missing.");
        return 1;
    }

    var process = Process.Start(new ProcessStartInfo
    {
        FileName = "python",
        Arguments = $"\"{ui}\"",
        WorkingDirectory = repoRoot,
        UseShellExecute = false,
        CreateNoWindow = true
    });

    if (process == null)
    {
        ShowError("Failed to open Zero OS.");
        return 1;
    }

    return 0;
}

static int OpenNativeShell(string repoRoot)
{
    var nativeExe = Path.Combine(repoRoot, "native_ui", "ZeroOS.NativeShell", "publish", "ZeroOS.NativeShell.exe");
    if (File.Exists(nativeExe))
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = nativeExe,
            WorkingDirectory = Path.GetDirectoryName(nativeExe) ?? repoRoot,
            UseShellExecute = true
        });
        return 0;
    }

    return OpenZeroOs(repoRoot);
}

static (int ExitCode, string Stdout, string Stderr) RunHidden(string fileName, string arguments, string workingDirectory)
{
    using var process = Process.Start(new ProcessStartInfo
    {
        FileName = fileName,
        Arguments = arguments,
        WorkingDirectory = workingDirectory,
        RedirectStandardOutput = true,
        RedirectStandardError = true,
        UseShellExecute = false,
        CreateNoWindow = true
    });

    if (process == null)
    {
        return (1, string.Empty, "Failed to start process.");
    }

    var stdout = process.StandardOutput.ReadToEnd();
    var stderr = process.StandardError.ReadToEnd();
    process.WaitForExit();
    return (process.ExitCode, stdout, stderr);
}

static string ResolveRepoRoot()
{
    var current = AppContext.BaseDirectory;
    var dir = new DirectoryInfo(current);
    while (dir != null)
    {
        if (File.Exists(Path.Combine(dir.FullName, "zero_os_ui.py")))
        {
            return dir.FullName;
        }
        dir = dir.Parent;
    }

    return AppContext.BaseDirectory;
}

static void ShowError(string message)
{
    MessageBox.Show(message, "Zero OS Launcher", MessageBoxButtons.OK, MessageBoxIcon.Error);
}
