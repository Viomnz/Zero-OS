using System.Text;
using System.IO;

namespace ZeroOS.NativeShell;

public sealed class NativeDiagnostics
{
    private readonly string _logDir;
    private readonly string _sessionLogPath;

    public NativeDiagnostics(string repoRoot)
    {
        _logDir = Path.Combine(repoRoot, ".zero_os", "native_shell");
        Directory.CreateDirectory(_logDir);
        _sessionLogPath = Path.Combine(_logDir, $"session_{DateTime.UtcNow:yyyyMMddTHHmmssZ}.log");
    }

    public string CrashMarkerPath => Path.Combine(_logDir, "last_crash.log");

    public void Append(string level, string message)
    {
        var line = $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] [{level}] {message}{Environment.NewLine}";
        File.AppendAllText(_sessionLogPath, line, Encoding.UTF8);
    }

    public void RecordCrash(Exception ex)
    {
        var text = new StringBuilder()
            .AppendLine($"time={DateTime.UtcNow:O}")
            .AppendLine(ex.ToString())
            .ToString();
        File.WriteAllText(CrashMarkerPath, text, Encoding.UTF8);
        Append("ERROR", ex.ToString());
    }

    public string? ConsumeCrashMarker()
    {
        if (!File.Exists(CrashMarkerPath))
        {
            return null;
        }

        var text = File.ReadAllText(CrashMarkerPath, Encoding.UTF8);
        File.Delete(CrashMarkerPath);
        return text;
    }
}
