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
        if (entries.Count == 0)
        {
            return "No share bundles yet.\n\nCreate a share zip to populate this panel.";
        }

        var lines = new List<string>
        {
            $"Repository: {repoUrl}",
            $"Releases: {releasesUrl}",
            "",
            "Latest artifacts:"
        };

        foreach (var item in entries.Take(10))
        {
            var kind = item.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) ? "ZIP" : "DIR";
            lines.Add($"[{kind}] {Path.GetFileName(item)}");
        }

        lines.Add("");
        lines.Add("Tag workflow:");
        lines.Add("git tag v1.0.0");
        lines.Add("git push origin v1.0.0");
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
