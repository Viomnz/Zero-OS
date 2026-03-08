using System.Diagnostics;
using System.IO;
using System.Text.Json;

namespace ZeroOS.NativeShell;

public sealed class NativeBackend
{
    public NativeBackend(string repoRoot)
    {
        RepoRoot = repoRoot;
        DistPath = Path.Combine(repoRoot, "dist");
        Directory.CreateDirectory(DistPath);
    }

    public string RepoRoot { get; }
    public string DistPath { get; }

    public NativeCommandResult RunTask(string task)
    {
        var process = new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"src/main.py \"{task}\"",
            WorkingDirectory = RepoRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        using var started = Process.Start(process);
        if (started == null)
        {
            return new NativeCommandResult(task, false, "Failed to start process.", null, null, "Failed to start process.");
        }

        var stdout = started.StandardOutput.ReadToEnd();
        var stderr = started.StandardError.ReadToEnd();
        started.WaitForExit();

        return ParseCommandResult(task, started.ExitCode, stdout, stderr);
    }

    public IReadOnlyList<string> ArtifactEntries()
    {
        return Directory.Exists(DistPath)
            ? Directory.GetFileSystemEntries(DistPath, "zero_os_bundle_*")
                .OrderByDescending(File.GetLastWriteTime)
                .ToList()
            : Array.Empty<string>();
    }

    public string LoadGithubIntegrationData()
    {
        var path = Path.Combine(RepoRoot, ".zero_os", "integrations", "github.json");
        return TryFormatJsonFile(path, "No GitHub integration file found.");
    }

    public string LoadReleaseData(string repoUrl, string releasesUrl)
    {
        var entries = ArtifactEntries();
        var installersDir = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "installers");
        var portableInstallers = Directory.Exists(installersDir)
            ? Directory.GetFiles(installersDir, "*.zip").OrderByDescending(File.GetLastWriteTime).ToList()
            : new List<string>();
        var msixDir = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "msix");
        var msixPackages = Directory.Exists(msixDir)
            ? Directory.GetFiles(msixDir, "*.msix").OrderByDescending(File.GetLastWriteTime).ToList()
            : new List<string>();

        var lines = new List<string>
        {
            $"Repository: {repoUrl}",
            $"Releases: {releasesUrl}",
            "",
            "Download paths:",
            $"- Portable installers ready: {portableInstallers.Count}",
            $"- MSIX packages ready: {msixPackages.Count}",
            $"- Share artifacts ready: {entries.Count}",
            "",
            "Latest native installers:"
        };

        if (portableInstallers.Count == 0)
        {
            lines.Add("- none yet");
        }
        else
        {
            foreach (var item in portableInstallers.Take(5))
            {
                lines.Add($"[PORTABLE] {Path.GetFileName(item)}");
            }
        }

        lines.Add("");
        lines.Add("Latest MSIX packages:");
        if (msixPackages.Count == 0)
        {
            lines.Add("- none yet");
        }
        else
        {
            foreach (var item in msixPackages.Take(5))
            {
                lines.Add($"[MSIX] {Path.GetFileName(item)}");
            }
        }

        lines.Add("");
        lines.Add("Latest Zero OS share artifacts:");
        if (entries.Count == 0)
        {
            lines.Add("- none yet");
        }
        foreach (var item in entries.Take(10))
        {
            var kind = item.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) ? "ZIP" : "DIR";
            lines.Add($"[{kind}] {Path.GetFileName(item)}");
        }

        lines.Add("");
        lines.Add("Release workflow:");
        lines.Add("git tag v1.0.0");
        lines.Add("git push origin v1.0.0");
        lines.Add("Tagged releases upload native publish output, portable installers, and MSIX packages.");
        return string.Join(Environment.NewLine, lines);
    }

    public string LoadProductStatus(string projectFile)
    {
        var lines = new List<string>();
        var version = ReadProjectVersion(projectFile) ?? "unknown";
        lines.Add($"Native shell version: {version}");
        lines.Add($"Update channel: {ReadUpdateChannel()}");

        var latest = ArtifactEntries().FirstOrDefault();
        if (latest == null)
        {
            lines.Add("Latest share artifact: none yet");
            lines.Add("Release readiness: waiting for first bundle");
            lines.Add("Update status: no newer local artifact detected");
        }
        else
        {
            lines.Add($"Latest share artifact: {Path.GetFileName(latest)}");
            lines.Add($"Last artifact time: {File.GetLastWriteTime(latest)}");
            lines.Add("Release readiness: bundle available");
            lines.Add($"Update status: {DescribeLocalUpdateState(projectFile, latest)}");
        }

        var releaseContracts = Path.Combine(RepoRoot, "zero_os_config", "release_contracts.json");
        lines.Add($"Release contracts: {(File.Exists(releaseContracts) ? "present" : "missing")}");

        var releaseWorkflow = Path.Combine(RepoRoot, ".github", "workflows", "release-share-bundle.yml");
        lines.Add($"Release workflow: {(File.Exists(releaseWorkflow) ? "present" : "missing")}");

        var nativeWorkflow = Path.Combine(RepoRoot, ".github", "workflows", "native-shell-windows.yml");
        lines.Add($"Native shell workflow: {(File.Exists(nativeWorkflow) ? "present" : "missing")}");

        var publishScript = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "publish.ps1");
        var msixScript = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "package_msix.ps1");
        var portableScript = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "package_portable.ps1");
        var publishDir = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "publish");
        var msixDir = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "msix");
        var installersDir = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "installers");
        var manifestPath = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "Package.appxmanifest");
        var assetsDir = Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "assets");
        lines.Add($"Publish script: {(File.Exists(publishScript) ? "present" : "missing")}");
        lines.Add($"MSIX script: {(File.Exists(msixScript) ? "present" : "missing")}");
        lines.Add($"Portable package script: {(File.Exists(portableScript) ? "present" : "missing")}");
        lines.Add($"Publish output: {(Directory.Exists(publishDir) ? "present" : "missing")}");
        lines.Add($"MSIX scaffold: {(Directory.Exists(msixDir) ? "present" : "missing")}");
        lines.Add($"Portable installers: {(Directory.Exists(installersDir) ? "present" : "missing")}");
        var latestInstaller = FindLatestPortableInstaller(installersDir);
        lines.Add($"Latest portable installer: {(string.IsNullOrWhiteSpace(latestInstaller) ? "none yet" : latestInstaller)}");
        lines.Add("");
        lines.Add("MSIX readiness:");
        lines.Add($"- Manifest: {(File.Exists(manifestPath) ? "present" : "missing")}");
        foreach (var assetLine in DescribeWindowsAssets(assetsDir))
        {
            lines.Add(assetLine);
        }
        lines.Add($"- Signing certificate flow: {(HasSigningReadiness(RepoRoot) ? "present" : "missing")}");
        lines.Add($"- Signing config: {(File.Exists(Path.Combine(RepoRoot, "native_ui", "ZeroOS.NativeShell", "signing.json")) ? "present" : "missing")}");

        return string.Join(Environment.NewLine, lines);
    }

    private static NativeCommandResult ParseCommandResult(string task, int exitCode, string stdout, string stderr)
    {
        var combined = string.IsNullOrWhiteSpace(stderr) ? stdout.Trim() : $"{stdout.Trim()}{Environment.NewLine}{stderr.Trim()}".Trim();
        JsonElement? payload = null;
        string? summary = combined;

        var lines = stdout.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
        if (lines.Length > 1 && lines[0].StartsWith("lane=", StringComparison.OrdinalIgnoreCase))
        {
            var candidate = string.Join(Environment.NewLine, lines.Skip(1)).Trim();
            if (!string.IsNullOrWhiteSpace(candidate))
            {
                summary = candidate;
                try
                {
                    payload = JsonSerializer.Deserialize<JsonElement>(candidate);
                }
                catch
                {
                }
            }
        }
        else if (!string.IsNullOrWhiteSpace(stdout))
        {
            try
            {
                payload = JsonSerializer.Deserialize<JsonElement>(stdout);
            }
            catch
            {
            }
        }

        return new NativeCommandResult(
            task,
            exitCode == 0,
            summary ?? string.Empty,
            payload,
            string.IsNullOrWhiteSpace(stdout) ? null : stdout.Trim(),
            string.IsNullOrWhiteSpace(stderr) ? null : stderr.Trim()
        );
    }

    private static string TryFormatJsonFile(string path, string missingMessage)
    {
        if (!File.Exists(path))
        {
            return missingMessage;
        }

        try
        {
            var parsed = JsonSerializer.Deserialize<JsonElement>(File.ReadAllText(path));
            return JsonSerializer.Serialize(parsed, new JsonSerializerOptions { WriteIndented = true });
        }
        catch (Exception ex)
        {
            return $"Failed to read JSON data.{Environment.NewLine}{ex.Message}";
        }
    }

    private static string? ReadProjectVersion(string projectFile)
    {
        if (!File.Exists(projectFile))
        {
            return null;
        }

        var text = File.ReadAllText(projectFile);
        var startTag = "<Version>";
        var endTag = "</Version>";
        var start = text.IndexOf(startTag, StringComparison.OrdinalIgnoreCase);
        var end = text.IndexOf(endTag, StringComparison.OrdinalIgnoreCase);
        if (start < 0 || end <= start)
        {
            return null;
        }

        start += startTag.Length;
        return text[start..end].Trim();
    }

    private string ReadUpdateChannel()
    {
        var path = Path.Combine(RepoRoot, "zero_os_config", "update_channels.json");
        if (!File.Exists(path))
        {
            return "unknown";
        }

        try
        {
            var parsed = JsonSerializer.Deserialize<JsonElement>(File.ReadAllText(path));
            if (parsed.TryGetProperty("channel", out var channel))
            {
                return channel.GetString() ?? "unknown";
            }
        }
        catch
        {
        }

        return "unknown";
    }

    private string DescribeLocalUpdateState(string projectFile, string latestArtifact)
    {
        try
        {
            var projectTime = File.Exists(projectFile) ? File.GetLastWriteTime(projectFile) : DateTime.MinValue;
            var artifactTime = File.GetLastWriteTime(latestArtifact);
            if (artifactTime > projectTime)
            {
                return "newer local release artifact available";
            }
        }
        catch
        {
        }

        return "native shell is aligned with latest local artifact";
    }

    private static IEnumerable<string> DescribeWindowsAssets(string assetsDir)
    {
        var required = new[]
        {
            "Square44x44Logo.png",
            "Square150x150Logo.png",
            "Wide310x150Logo.png",
            "SplashScreen.png",
            "app_icon.ico",
        };

        foreach (var name in required)
        {
            yield return $"- Asset {name}: {(File.Exists(Path.Combine(assetsDir, name)) ? "present" : "missing")}";
        }
    }

    private static bool HasSigningReadiness(string repoRoot)
    {
        var paths = new[]
        {
            Path.Combine(repoRoot, "native_ui", "ZeroOS.NativeShell", "msix", "README.txt"),
            Path.Combine(repoRoot, ".github", "workflows", "native-shell-windows.yml"),
            Path.Combine(repoRoot, "native_ui", "ZeroOS.NativeShell", "signing.json"),
        };
        return paths.All(File.Exists);
    }

    private static string? FindLatestPortableInstaller(string installersDir)
    {
        if (!Directory.Exists(installersDir))
        {
            return null;
        }

        var latest = Directory.GetFiles(installersDir, "*.zip")
            .OrderByDescending(File.GetLastWriteTime)
            .FirstOrDefault();
        return latest == null ? null : Path.GetFileName(latest);
    }
}

public sealed record NativeCommandResult(
    string Task,
    bool Ok,
    string Summary,
    JsonElement? Payload,
    string? RawStdout,
    string? RawStderr
)
{
    public string DisplayText()
    {
        if (Payload.HasValue)
        {
            return JsonSerializer.Serialize(Payload.Value, new JsonSerializerOptions { WriteIndented = true });
        }

        if (!string.IsNullOrWhiteSpace(Summary))
        {
            return Summary;
        }

        return RawStderr ?? RawStdout ?? string.Empty;
    }
}
