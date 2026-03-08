using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace ZeroOS.NativeShell;

public partial class MainWindow : Window
{
    private const string RepoUrl = "https://github.com/Viomnz/Zero-OS";
    private const string ReleasesUrl = "https://github.com/Viomnz/Zero-OS/releases";
    private const string CloneCommand = "git clone https://github.com/Viomnz/Zero-OS.git";
    private const string FirstRunCommand = @".\zero_os_launcher.ps1 first-run";
    private const string OpenShellCommand = "Start-Process \".\\zero_os_shell.html\"";
    private const string PublishCommand = @".\publish.ps1";
    private const string MsixCommand = @".\package_msix.ps1";
    private readonly string _projectFile;

    private readonly string _repoRoot;
    private readonly string _nativeUiRoot;
    private readonly NativeBackend _backend;
    private readonly NativeDiagnostics _diagnostics;
    private readonly ObservableCollection<string> _logs = new();
    private string? _activeWorkspacePath;
    private bool _activeWorkspacePathEditable;
    private bool _workspaceDirty;
    private bool _suspendWorkspaceDirtyTracking;

    private static readonly HashSet<string> SkipRoots = new(StringComparer.OrdinalIgnoreCase)
    {
        ".git", ".zero_os", "bin", "obj"
    };

    private static readonly HashSet<string> PreviewSuffixes = new(StringComparer.OrdinalIgnoreCase)
    {
        ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".ps1", ".py", ".html", ".css", ".js", ".cs", ".xaml", ".csproj"
    };

    public MainWindow()
    {
        InitializeComponent();
        _repoRoot = ResolveRepoRoot();
        _nativeUiRoot = Path.Combine(_repoRoot, "native_ui", "ZeroOS.NativeShell");
        _projectFile = Path.Combine(_repoRoot, "native_ui", "ZeroOS.NativeShell", "ZeroOS.NativeShell.csproj");
        _backend = new NativeBackend(_repoRoot);
        _diagnostics = new NativeDiagnostics(_repoRoot);

        var crashReport = _diagnostics.ConsumeCrashMarker();
        if (!string.IsNullOrWhiteSpace(crashReport))
        {
            MessageBox.Show(
                "Zero OS Native Shell recovered from a previous crash.\n\nA crash log was saved under .zero_os/native_shell.",
                "Recovered Session",
                MessageBoxButton.OK,
                MessageBoxImage.Warning
            );
        }

        RefreshArtifacts();
        RefreshWorkspaceTree();
        RefreshGithubData();
        RefreshReleaseData();
        RefreshSecuritySpecs();
        SetStatus("Ready");
        AppendLog("Application started");
    }

    private string ResolveRepoRoot()
    {
        var current = AppContext.BaseDirectory;
        var dir = new DirectoryInfo(current);
        while (dir != null)
        {
            if (File.Exists(Path.Combine(dir.FullName, "zero_os_launcher.ps1")))
            {
                return dir.FullName;
            }
            dir = dir.Parent;
        }
        return AppContext.BaseDirectory;
    }

    private void CopyCloneCommand_Click(object sender, RoutedEventArgs e) => CopyText(CloneCommand, "clone command");
    private void CopyFirstRun_Click(object sender, RoutedEventArgs e) => CopyText(FirstRunCommand, "first-run command");
    private void CopyOpenShell_Click(object sender, RoutedEventArgs e) => CopyText(OpenShellCommand, "open shell command");

    private void OpenRepository_Click(object sender, RoutedEventArgs e) => OpenUrl(RepoUrl);
    private void OpenReleases_Click(object sender, RoutedEventArgs e) => OpenUrl(ReleasesUrl);

    private void RefreshGithubData_Click(object sender, RoutedEventArgs e)
    {
        RefreshGithubData();
        SetStatus("GitHub data refreshed.");
    }

    private void RefreshReleaseData_Click(object sender, RoutedEventArgs e)
    {
        RefreshReleaseData();
        SetStatus("Release data refreshed.");
    }

    private void RefreshSecuritySpecs_Click(object sender, RoutedEventArgs e)
    {
        RefreshSecuritySpecs();
        SetStatus("Security specs refreshed.");
    }

    private void CopyPublishCommand_Click(object sender, RoutedEventArgs e) => CopyText(PublishCommand, "publish command");
    private void CopyMsixCommand_Click(object sender, RoutedEventArgs e) => CopyText(MsixCommand, "MSIX command");

    private void BuildNativePublish_Click(object sender, RoutedEventArgs e)
    {
        RunNativeScript("publish.ps1", "Native publish complete");
    }

    private void CreateNativeMsix_Click(object sender, RoutedEventArgs e)
    {
        RunNativeScript("package_msix.ps1", "MSIX scaffold complete");
    }

    private void ExportBundle_Click(object sender, RoutedEventArgs e) => RunBackendTask("zero os export bundle", "Export bundle complete");
    private void CreateShareZip_Click(object sender, RoutedEventArgs e) => RunBackendTask("zero os share package", "Share zip complete");
    private void CoreStatus_Click(object sender, RoutedEventArgs e) => RunBackendTask("core status", "Core status loaded");
    private void GithubStatus_Click(object sender, RoutedEventArgs e) => RunBackendTask("github status", "GitHub status loaded");

    private void OpenDist_Click(object sender, RoutedEventArgs e)
    {
        OpenPath(_backend.DistPath);
        SetStatus("Opened dist folder.");
        AppendLog("Opened dist folder");
    }

    private void OpenNativePublishFolder_Click(object sender, RoutedEventArgs e)
    {
        OpenPath(Path.Combine(_nativeUiRoot, "publish"));
        SetStatus("Opened native publish folder.");
    }

    private void OpenNativeMsixFolder_Click(object sender, RoutedEventArgs e)
    {
        OpenPath(Path.Combine(_nativeUiRoot, "msix"));
        SetStatus("Opened MSIX scaffold folder.");
    }

    private void OpenSigningConfig_Click(object sender, RoutedEventArgs e)
    {
        OpenPath(Path.Combine(_nativeUiRoot, "signing.json"));
        SetStatus("Opened signing config.");
    }

    private void RefreshArtifacts_Click(object sender, RoutedEventArgs e)
    {
        RefreshArtifacts();
        SetStatus("Artifacts refreshed.");
        AppendLog("Artifacts refreshed");
    }

    private void OpenCureFirewallSource_Click(object sender, RoutedEventArgs e)
    {
        OpenPath(Path.Combine(_repoRoot, "src", "zero_os", "cure_firewall.py"));
        SetStatus("Opened Cure Firewall source.");
    }

    private void OpenAntivirusSource_Click(object sender, RoutedEventArgs e)
    {
        OpenPath(Path.Combine(_repoRoot, "src", "zero_os", "antivirus.py"));
        SetStatus("Opened Antivirus source.");
    }

    private void RefreshFiles_Click(object sender, RoutedEventArgs e)
    {
        RefreshWorkspaceTree();
        SetStatus("Workspace files refreshed.");
    }

    private void SaveWorkspaceFile_Click(object sender, RoutedEventArgs e)
    {
        if (!_activeWorkspacePathEditable || string.IsNullOrWhiteSpace(_activeWorkspacePath) || !File.Exists(_activeWorkspacePath))
        {
            SetStatus("Select an editable text file first.");
            return;
        }

        try
        {
            File.WriteAllText(_activeWorkspacePath, WorkspaceFileBox.Text);
            _workspaceDirty = false;
            WorkspaceEditorStatusText.Text = $"Saved: {Path.GetRelativePath(_repoRoot, _activeWorkspacePath)}";
            SetStatus($"Saved {Path.GetFileName(_activeWorkspacePath)}");
            AppendLog($"Saved workspace file {Path.GetRelativePath(_repoRoot, _activeWorkspacePath)}");
            RefreshWorkspaceTree();
            RenderWorkspacePath(_activeWorkspacePath);
        }
        catch (Exception ex)
        {
            WorkspaceEditorStatusText.Text = $"Save failed: {ex.Message}";
            SetStatus("Save failed.");
            AppendLog($"Failed to save workspace file: {ex.Message}");
        }
    }

    private void NewWorkspaceFile_Click(object sender, RoutedEventArgs e)
    {
        var relativePath = PromptForText("Create New File", "Enter a relative path inside the Zero OS workspace:", "notes/new_file.txt");
        if (string.IsNullOrWhiteSpace(relativePath))
        {
            return;
        }

        var normalized = relativePath.Replace('/', Path.DirectorySeparatorChar).Trim();
        var targetPath = Path.GetFullPath(Path.Combine(_repoRoot, normalized));
        if (!targetPath.StartsWith(_repoRoot, StringComparison.OrdinalIgnoreCase))
        {
            SetStatus("New file must stay inside the Zero OS workspace.");
            return;
        }

        try
        {
            var parent = Path.GetDirectoryName(targetPath);
            if (!string.IsNullOrWhiteSpace(parent))
            {
                Directory.CreateDirectory(parent);
            }

            if (!File.Exists(targetPath))
            {
                File.WriteAllText(targetPath, string.Empty);
            }

            RefreshWorkspaceTree();
            RenderWorkspacePath(targetPath);
            SetStatus($"Created {Path.GetFileName(targetPath)}");
            AppendLog($"Created workspace file {Path.GetRelativePath(_repoRoot, targetPath)}");
        }
        catch (Exception ex)
        {
            WorkspaceEditorStatusText.Text = $"Create failed: {ex.Message}";
            SetStatus("Create file failed.");
            AppendLog($"Failed to create workspace file: {ex.Message}");
        }
    }

    private void NewWorkspaceFolder_Click(object sender, RoutedEventArgs e)
    {
        var relativePath = PromptForText("Create New Folder", "Enter a relative folder path inside the Zero OS workspace:", "notes/new_folder");
        if (string.IsNullOrWhiteSpace(relativePath))
        {
            return;
        }

        var targetPath = NormalizeWorkspacePath(relativePath);
        if (targetPath == null)
        {
            SetStatus("New folder must stay inside the Zero OS workspace.");
            return;
        }

        try
        {
            Directory.CreateDirectory(targetPath);
            RefreshWorkspaceTree();
            RenderWorkspacePath(targetPath);
            SetStatus($"Created folder {Path.GetFileName(targetPath)}");
            AppendLog($"Created workspace folder {Path.GetRelativePath(_repoRoot, targetPath)}");
        }
        catch (Exception ex)
        {
            SetStatus("Create folder failed.");
            AppendLog($"Failed to create workspace folder: {ex.Message}");
        }
    }

    private void RenameWorkspacePath_Click(object sender, RoutedEventArgs e)
    {
        var path = CurrentWorkspacePath();
        if (path == null)
        {
            SetStatus("Select a workspace file or folder first.");
            return;
        }

        if (!EnsureWorkspaceSelectionCanChange())
        {
            return;
        }

        var currentName = Path.GetFileName(path.TrimEnd(Path.DirectorySeparatorChar));
        var newName = PromptForText("Rename Path", "Enter the new file or folder name:", currentName);
        if (string.IsNullOrWhiteSpace(newName))
        {
            return;
        }

        var parent = Directory.Exists(path) ? Directory.GetParent(path)?.FullName : Path.GetDirectoryName(path);
        if (string.IsNullOrWhiteSpace(parent))
        {
            SetStatus("Rename failed: invalid parent path.");
            return;
        }

        var targetPath = NormalizeWorkspacePath(Path.Combine(parent, newName));
        if (targetPath == null)
        {
            SetStatus("Rename target must stay inside the Zero OS workspace.");
            return;
        }

        try
        {
            if (Directory.Exists(path))
            {
                Directory.Move(path, targetPath);
            }
            else if (File.Exists(path))
            {
                File.Move(path, targetPath);
            }
            else
            {
                SetStatus("Selected path no longer exists.");
                return;
            }

            RefreshWorkspaceTree();
            RenderWorkspacePath(targetPath);
            SetStatus($"Renamed to {Path.GetFileName(targetPath)}");
            AppendLog($"Renamed workspace path to {Path.GetRelativePath(_repoRoot, targetPath)}");
        }
        catch (Exception ex)
        {
            SetStatus("Rename failed.");
            AppendLog($"Failed to rename workspace path: {ex.Message}");
        }
    }

    private void DeleteWorkspacePath_Click(object sender, RoutedEventArgs e)
    {
        var path = CurrentWorkspacePath();
        if (path == null)
        {
            SetStatus("Select a workspace file or folder first.");
            return;
        }

        if (!EnsureWorkspaceSelectionCanChange())
        {
            return;
        }

        var result = MessageBox.Show(
            $"Delete '{Path.GetFileName(path.TrimEnd(Path.DirectorySeparatorChar))}' from the Zero OS workspace?",
            "Delete Path",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning
        );

        if (result != MessageBoxResult.Yes)
        {
            return;
        }

        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
            else if (File.Exists(path))
            {
                File.Delete(path);
            }
            else
            {
                SetStatus("Selected path no longer exists.");
                return;
            }

            RefreshWorkspaceTree();
            SetStatus("Workspace path deleted.");
            AppendLog($"Deleted workspace path {Path.GetRelativePath(_repoRoot, path)}");
        }
        catch (Exception ex)
        {
            SetStatus("Delete failed.");
            AppendLog($"Failed to delete workspace path: {ex.Message}");
        }
    }

    private void SearchWorkspace_Click(object sender, RoutedEventArgs e) => RunWorkspaceSearch();

    private void ClearWorkspaceSearch_Click(object sender, RoutedEventArgs e)
    {
        WorkspaceSearchBox.Text = string.Empty;
        WorkspaceSearchResultsListBox.ItemsSource = null;
        ResetWorkspaceEditorState();
        WorkspaceFileBox.Text = $"Workspace root: {_repoRoot}";
        SetStatus("Workspace search cleared.");
    }

    private void WorkspaceSearchResultsListBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (WorkspaceSearchResultsListBox.SelectedItem is not string item || string.IsNullOrWhiteSpace(item))
        {
            return;
        }

        if (!EnsureWorkspaceSelectionCanChange())
        {
            return;
        }

        var path = item.Split("  |  ")[0];
        RenderWorkspacePath(path);
    }

    private void WorkspaceTreeView_SelectedItemChanged(object sender, RoutedPropertyChangedEventArgs<object> e)
    {
        if (!EnsureWorkspaceSelectionCanChange())
        {
            e.Handled = true;
            return;
        }

        RenderWorkspaceSelection();
    }

    private void OpenWorkspacePath_Click(object sender, RoutedEventArgs e)
    {
        var path = CurrentWorkspacePath();
        if (path == null)
        {
            SetStatus("Select a workspace file or folder first.");
            return;
        }
        OpenPath(path);
        SetStatus($"Opened {Path.GetFileName(path)}");
    }

    private void RevealWorkspacePath_Click(object sender, RoutedEventArgs e)
    {
        var path = CurrentWorkspacePath();
        if (path == null)
        {
            SetStatus("Select a workspace file or folder first.");
            return;
        }
        RevealPath(path);
        SetStatus($"Revealed {Path.GetFileName(path)}");
    }

    private void CopyWorkspacePath_Click(object sender, RoutedEventArgs e)
    {
        var path = CurrentWorkspacePath();
        if (path == null)
        {
            SetStatus("Select a workspace file or folder first.");
            return;
        }
        CopyText(path, "workspace path");
    }

    private void OpenArtifact_Click(object sender, RoutedEventArgs e)
    {
        var path = SelectedArtifactPath();
        if (path == null)
        {
            SetStatus("Select an artifact first.");
            return;
        }
        OpenPath(path);
        SetStatus($"Opened {Path.GetFileName(path)}");
        AppendLog($"Opened artifact {Path.GetFileName(path)}");
    }

    private void RevealArtifact_Click(object sender, RoutedEventArgs e)
    {
        var path = SelectedArtifactPath();
        if (path == null)
        {
            SetStatus("Select an artifact first.");
            return;
        }
        RevealPath(path);
        SetStatus($"Revealed {Path.GetFileName(path)}");
        AppendLog($"Revealed artifact {Path.GetFileName(path)}");
    }

    private void CopyArtifactPath_Click(object sender, RoutedEventArgs e)
    {
        var path = SelectedArtifactPath();
        if (path == null)
        {
            SetStatus("Select an artifact first.");
            return;
        }
        CopyText(path, "artifact path");
    }

    private void ArtifactsListBox_SelectionChanged(object sender, SelectionChangedEventArgs e) => RenderArtifactDetails();

    private void CopyText(string text, string label)
    {
        Clipboard.SetText(text);
        SetStatus($"Copied {label}.");
        OutputBox.Text = text;
        AppendLog($"Copied {label}");
    }

    private void OpenUrl(string url)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = url,
            UseShellExecute = true
        });
        SetStatus($"Opened {url}");
        OutputBox.Text = url;
        AppendLog($"Opened URL {url}");
    }

    private static void OpenPath(string path)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = path,
            UseShellExecute = true
        });
    }

    private static void RevealPath(string path)
    {
        Process.Start(new ProcessStartInfo
        {
            FileName = "explorer.exe",
            Arguments = $"/select,\"{path}\"",
            UseShellExecute = true
        });
    }

    private void RunBackendTask(string command, string successMessage)
    {
        SetStatus($"Running: {command}");
        AppendLog($"Running command: {command}");
        var result = _backend.RunTask(command);
        OutputBox.Text = result.DisplayText();
        if (result.Ok)
        {
            SetStatus(successMessage);
            AppendLog(successMessage);
        }
        else
        {
            SetStatus("Command completed. Review output.");
            AppendLog("Command completed with review-needed output");
        }
        RefreshArtifacts();
        RefreshGithubData();
        RefreshReleaseData();
    }

    private void RunNativeScript(string scriptName, string successMessage)
    {
        var scriptPath = Path.Combine(_nativeUiRoot, scriptName);
        if (!File.Exists(scriptPath))
        {
            SetStatus($"Missing native script: {scriptName}");
            return;
        }

        SetStatus($"Running native script: {scriptName}");
        AppendLog($"Running native script: {scriptName}");

        var psi = new ProcessStartInfo
        {
            FileName = "powershell",
            Arguments = $"-ExecutionPolicy Bypass -File \"{scriptPath}\"",
            WorkingDirectory = _nativeUiRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        using var process = Process.Start(psi);
        if (process == null)
        {
            SetStatus("Failed to start native script.");
            return;
        }

        var stdout = process.StandardOutput.ReadToEnd();
        var stderr = process.StandardError.ReadToEnd();
        process.WaitForExit();

        OutputBox.Text = string.IsNullOrWhiteSpace(stderr) ? stdout.Trim() : $"{stdout.Trim()}{Environment.NewLine}{stderr.Trim()}".Trim();
        if (process.ExitCode == 0)
        {
            SetStatus(successMessage);
            AppendLog(successMessage);
        }
        else
        {
            SetStatus("Native script completed with errors.");
            AppendLog($"Native script failed: {scriptName}");
        }

        RefreshReleaseData();
    }

    private void RefreshArtifacts()
    {
        var items = _backend.ArtifactEntries();
        ArtifactsListBox.ItemsSource = items.Select(Path.GetFileName).ToList();
        if (items.Count > 0 && ArtifactsListBox.SelectedIndex < 0)
        {
            ArtifactsListBox.SelectedIndex = 0;
        }
        RenderArtifactDetails();
    }

    private void RefreshGithubData()
    {
        GithubDataBox.Text = _backend.LoadGithubIntegrationData();
    }

    private void RefreshWorkspaceTree()
    {
        WorkspaceTreeView.Items.Clear();
        var root = BuildTreeNode(new DirectoryInfo(_repoRoot), includeFiles: true, depth: 0);
        if (root != null)
        {
            WorkspaceTreeView.Items.Add(root);
            root.IsExpanded = true;
        }
        ResetWorkspaceEditorState();
        WorkspaceFileBox.Text = $"Workspace root: {_repoRoot}";
    }

    private TreeViewItem? BuildTreeNode(DirectoryInfo dir, bool includeFiles, int depth)
    {
        if (SkipRoots.Contains(dir.Name) && depth > 0)
        {
            return null;
        }

        var node = new TreeViewItem
        {
            Header = dir.Name,
            Tag = dir.FullName
        };

        try
        {
            foreach (var sub in dir.GetDirectories().OrderBy(d => d.Name))
            {
                var child = BuildTreeNode(sub, includeFiles, depth + 1);
                if (child != null)
                {
                    node.Items.Add(child);
                }
            }

            if (includeFiles)
            {
                foreach (var file in dir.GetFiles().OrderBy(f => f.Name))
                {
                    node.Items.Add(new TreeViewItem
                    {
                        Header = file.Name,
                        Tag = file.FullName
                    });
                }
            }
        }
        catch
        {
            node.Items.Add(new TreeViewItem { Header = "[access denied]" });
        }

        return node;
    }

    private string? SelectedWorkspacePath() => (WorkspaceTreeView.SelectedItem as TreeViewItem)?.Tag as string;

    private string? CurrentWorkspacePath()
    {
        return !string.IsNullOrWhiteSpace(_activeWorkspacePath) ? _activeWorkspacePath : SelectedWorkspacePath();
    }

    private void RenderWorkspaceSelection()
    {
        var path = SelectedWorkspacePath();
        if (string.IsNullOrWhiteSpace(path))
        {
            WorkspaceFileBox.Text = "Select a file or folder from the Zero OS workspace.";
            return;
        }

        RenderWorkspacePath(path);
    }

    private void RenderWorkspacePath(string path)
    {
        ResetWorkspaceEditorState();
        _activeWorkspacePath = path;
        _suspendWorkspaceDirtyTracking = true;

        try
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                WorkspaceEditorStatusText.Text = "Select a file to edit it here.";
                WorkspaceFileBox.Text = "Select a file or folder from the Zero OS workspace.";
                return;
            }

            if (Directory.Exists(path))
            {
                var entries = Directory.GetFileSystemEntries(path).OrderBy(p => p).Take(200).ToList();
                var text = new StringBuilder();
                text.AppendLine($"Folder: {path}");
                text.AppendLine();
                foreach (var entry in entries)
                {
                    text.AppendLine(Path.GetFileName(entry));
                }
                WorkspaceEditorStatusText.Text = "Folders are browse-only. Select a text file to edit.";
                WorkspaceFileBox.Text = text.ToString();
                return;
            }

            if (!File.Exists(path))
            {
                WorkspaceEditorStatusText.Text = "Selected path no longer exists.";
                WorkspaceFileBox.Text = "Selected path no longer exists.";
                return;
            }

            var suffix = Path.GetExtension(path);
            if (!PreviewSuffixes.Contains(suffix))
            {
                WorkspaceEditorStatusText.Text = "This file type is preview-only and cannot be edited here.";
                WorkspaceFileBox.Text = $"File: {path}{Environment.NewLine}{Environment.NewLine}Preview disabled for this file type.";
                return;
            }

            var fileText = File.ReadAllText(path);
            if (fileText.Length > 40000)
            {
                WorkspaceEditorStatusText.Text = "Large file preview loaded in truncated mode. Save is disabled for safety.";
                WorkspaceFileBox.Text = fileText[..40000] + Environment.NewLine + Environment.NewLine + "[truncated]";
                return;
            }

            _activeWorkspacePathEditable = true;
            WorkspaceFileBox.IsReadOnly = false;
            WorkspaceEditorStatusText.Text = $"Editing: {Path.GetRelativePath(_repoRoot, path)}";
            WorkspaceFileBox.Text = fileText;
        }
        catch (Exception ex)
        {
            WorkspaceEditorStatusText.Text = "File preview failed.";
            WorkspaceFileBox.Text = $"Failed to read file.{Environment.NewLine}{ex.Message}";
        }
        finally
        {
            _suspendWorkspaceDirtyTracking = false;
        }
    }

    private void RunWorkspaceSearch()
    {
        var query = WorkspaceSearchBox.Text?.Trim() ?? string.Empty;
        if (string.IsNullOrWhiteSpace(query))
        {
            SetStatus("Enter a search term first.");
            return;
        }

        var results = new List<string>();
        try
        {
            foreach (var path in Directory.EnumerateFiles(_repoRoot, "*", SearchOption.AllDirectories))
            {
                if (results.Count >= 120)
                {
                    break;
                }

                var file = new FileInfo(path);
                if (SkipRoots.Contains(file.Directory?.Name ?? string.Empty))
                {
                    continue;
                }
                if (file.FullName.Split(Path.DirectorySeparatorChar).Any(part => SkipRoots.Contains(part)))
                {
                    continue;
                }

                var rel = Path.GetRelativePath(_repoRoot, file.FullName);
                var hit = rel.Contains(query, StringComparison.OrdinalIgnoreCase);
                string preview = string.Empty;

                if (!hit && PreviewSuffixes.Contains(file.Extension))
                {
                    try
                    {
                        var fileText = File.ReadAllText(file.FullName);
                        var idx = fileText.IndexOf(query, StringComparison.OrdinalIgnoreCase);
                        if (idx >= 0)
                        {
                            hit = true;
                            var start = Math.Max(0, idx - 50);
                            var len = Math.Min(140, fileText.Length - start);
                            preview = fileText.Substring(start, len).Replace(Environment.NewLine, " ");
                        }
                    }
                    catch
                    {
                    }
                }

                if (hit)
                {
                    results.Add(string.IsNullOrWhiteSpace(preview) ? rel : $"{rel}  |  {preview}");
                }
            }
        }
        catch (Exception ex)
        {
            WorkspaceSearchResultsListBox.ItemsSource = new[] { $"Search failed: {ex.Message}" };
            SetStatus("Workspace search failed.");
            return;
        }

        WorkspaceSearchResultsListBox.ItemsSource = results;
        SetStatus(results.Count == 0 ? "No search matches found." : $"Workspace search found {results.Count} matches.");
        AppendLog($"Workspace search for '{query}' returned {results.Count} matches");
    }

    private void RefreshReleaseData()
    {
        ReleaseDataBox.Text = _backend.LoadReleaseData(RepoUrl, ReleasesUrl);
        ReleaseStatusBox.Text = _backend.LoadProductStatus(_projectFile);
    }

    private void RefreshSecuritySpecs()
    {
        CureFirewallSpecBox.Text = BuildSecuritySpec(
            "Cure Firewall",
            Path.Combine(_repoRoot, "src", "zero_os", "cure_firewall.py"),
            new[]
            {
                Path.Combine(_repoRoot, "src", "zero_os", "cure_firewall_agent.py"),
                Path.Combine(_repoRoot, "src", "zero_os", "cure_firewall_full_auto.py"),
                Path.Combine(_repoRoot, "tests", "test_quantum_virus_curefirewall.py"),
                Path.Combine(_repoRoot, ".zero_os", "production", "znet_cure_report.json"),
            });

        AntivirusSpecBox.Text = BuildSecuritySpec(
            "Antivirus",
            Path.Combine(_repoRoot, "src", "zero_os", "antivirus.py"),
            new[]
            {
                Path.Combine(_repoRoot, "src", "zero_os", "antivirus_agent.py"),
                Path.Combine(_repoRoot, "tests", "test_antivirus_system.py"),
                Path.Combine(_repoRoot, ".zero_os", "antivirus", "policy.json"),
                Path.Combine(_repoRoot, ".zero_os", "antivirus", "threat_feed.json"),
                Path.Combine(_repoRoot, ".zero_os", "antivirus", "last_scan.json"),
            });
    }

    private string BuildSecuritySpec(string title, string primarySource, IEnumerable<string> relatedPaths)
    {
        var lines = new List<string> { $"{title} Spec", "" };
        var primary = new FileInfo(primarySource);
        if (primary.Exists)
        {
            lines.Add($"Primary source: {Path.GetRelativePath(_repoRoot, primary.FullName)}");
            lines.Add($"Size: {primary.Length} bytes");
            lines.Add($"Modified: {primary.LastWriteTime}");
            lines.Add("");
            lines.Add("Preview:");
            try
            {
                var text = File.ReadAllText(primary.FullName);
                lines.AddRange(text.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None).Take(40));
            }
            catch (Exception ex)
            {
                lines.Add($"Failed to read source preview: {ex.Message}");
            }
        }
        else
        {
            lines.Add("Primary source file not found.");
        }

        lines.Add("");
        lines.Add("Related files:");
        foreach (var path in relatedPaths)
        {
            lines.Add($"{(File.Exists(path) ? "[present]" : "[missing]")} {Path.GetRelativePath(_repoRoot, path)}");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private void AppendLog(string message)
    {
        var line = $"[{DateTime.Now:HH:mm:ss}] {message}";
        _logs.Add(line);
        while (_logs.Count > 80)
        {
            _logs.RemoveAt(0);
        }
        LogBox.Text = string.Join(Environment.NewLine, _logs);
        LogBox.ScrollToEnd();
        _diagnostics.Append("INFO", message);
    }

    private string? SelectedArtifactPath()
    {
        if (ArtifactsListBox.SelectedItem is not string name || string.IsNullOrWhiteSpace(name))
        {
            return null;
        }
        var path = Path.Combine(_backend.DistPath, name);
        return File.Exists(path) || Directory.Exists(path) ? path : null;
    }

    private void RenderArtifactDetails()
    {
        var path = SelectedArtifactPath();
        if (path == null)
        {
            ArtifactDetailsBox.Text = "No artifact selected.";
            return;
        }

        var lines = new List<string>
        {
            $"Name: {Path.GetFileName(path)}",
            $"Path: {path}",
            $"Kind: {(Directory.Exists(path) ? "Bundle directory" : "ZIP archive")}",
            $"Modified: {File.GetLastWriteTime(path)}"
        };

        if (File.Exists(path))
        {
            lines.Add($"Size: {new FileInfo(path).Length} bytes");
        }
        else
        {
            lines.Add($"Entries: {Directory.EnumerateFileSystemEntries(path, "*", SearchOption.AllDirectories).Count()}");
            var manifest = Path.Combine(path, "zero_os_share_manifest.json");
            if (File.Exists(manifest))
            {
                try
                {
                    var parsed = JsonSerializer.Deserialize<JsonElement>(File.ReadAllText(manifest));
                    lines.Add("");
                    lines.Add(JsonSerializer.Serialize(parsed, new JsonSerializerOptions { WriteIndented = true }));
                }
                catch
                {
                    lines.Add("");
                    lines.Add("Manifest present but could not be parsed.");
                }
            }
        }

        var securityFiles = FindSecurityBundleFiles(path).Take(40).ToList();
        lines.Add("");
        lines.Add("Cure Firewall + Antivirus bundle files:");
        if (securityFiles.Count == 0)
        {
            lines.Add("None detected in this artifact.");
        }
        else
        {
            lines.AddRange(securityFiles);
        }

        ArtifactDetailsBox.Text = string.Join(Environment.NewLine, lines);
    }

    private void SetStatus(string text)
    {
        StatusText.Text = text;
        AppendLog($"Status: {text}");
    }

    private void WorkspaceFileBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (_suspendWorkspaceDirtyTracking || !_activeWorkspacePathEditable)
        {
            return;
        }

        _workspaceDirty = true;
        if (!string.IsNullOrWhiteSpace(_activeWorkspacePath))
        {
            WorkspaceEditorStatusText.Text = $"Unsaved changes: {Path.GetRelativePath(_repoRoot, _activeWorkspacePath)}";
        }
    }

    private bool EnsureWorkspaceSelectionCanChange()
    {
        if (!_workspaceDirty || !_activeWorkspacePathEditable)
        {
            return true;
        }

        var result = MessageBox.Show(
            "You have unsaved changes in the current file. Continue without saving?",
            "Unsaved Changes",
            MessageBoxButton.YesNo,
            MessageBoxImage.Warning
        );

        if (result == MessageBoxResult.Yes)
        {
            _workspaceDirty = false;
            return true;
        }

        return false;
    }

    private void Window_Closing(object sender, CancelEventArgs e)
    {
        if (!EnsureWorkspaceSelectionCanChange())
        {
            e.Cancel = true;
        }
    }

    private void ResetWorkspaceEditorState()
    {
        _activeWorkspacePath = null;
        _activeWorkspacePathEditable = false;
        _workspaceDirty = false;
        _suspendWorkspaceDirtyTracking = true;
        WorkspaceFileBox.IsReadOnly = true;
        WorkspaceEditorStatusText.Text = "Text files can be edited here and saved back into the Zero OS workspace.";
    }

    private string? NormalizeWorkspacePath(string relativeOrAbsolutePath)
    {
        var candidate = Path.IsPathRooted(relativeOrAbsolutePath)
            ? Path.GetFullPath(relativeOrAbsolutePath)
            : Path.GetFullPath(Path.Combine(_repoRoot, relativeOrAbsolutePath.Replace('/', Path.DirectorySeparatorChar).Trim()));

        return candidate.StartsWith(_repoRoot, StringComparison.OrdinalIgnoreCase) ? candidate : null;
    }

    private IEnumerable<string> FindSecurityBundleFiles(string artifactPath)
    {
        static bool IsSecurityPath(string candidate)
        {
            return candidate.Contains("cure_firewall", StringComparison.OrdinalIgnoreCase)
                || candidate.Contains("antivirus", StringComparison.OrdinalIgnoreCase);
        }

        if (Directory.Exists(artifactPath))
        {
            foreach (var entry in Directory.EnumerateFiles(artifactPath, "*", SearchOption.AllDirectories))
            {
                var rel = Path.GetRelativePath(artifactPath, entry).Replace("\\", "/");
                if (IsSecurityPath(rel))
                {
                    yield return rel;
                }
            }
            yield break;
        }

        if (File.Exists(artifactPath) && string.Equals(Path.GetExtension(artifactPath), ".zip", StringComparison.OrdinalIgnoreCase))
        {
            using var archive = ZipFile.OpenRead(artifactPath);
            foreach (var entry in archive.Entries.OrderBy(e => e.FullName))
            {
                if (!string.IsNullOrWhiteSpace(entry.Name) && IsSecurityPath(entry.FullName))
                {
                    yield return entry.FullName.Replace("\\", "/");
                }
            }
        }
    }

    private string? PromptForText(string title, string message, string defaultValue)
    {
        var dialog = new Window
        {
            Title = title,
            Width = 460,
            Height = 190,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Owner = this,
            ResizeMode = ResizeMode.NoResize,
            Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#101B29"))
        };

        var layout = new Grid { Margin = new Thickness(16) };
        layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var messageBlock = new TextBlock
        {
            Text = message,
            Foreground = Brushes.White,
            TextWrapping = TextWrapping.Wrap
        };
        Grid.SetRow(messageBlock, 0);

        var inputBox = new TextBox
        {
            Margin = new Thickness(0, 12, 0, 12),
            Text = defaultValue,
            Background = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#0D1826")),
            Foreground = Brushes.White,
            BorderThickness = new Thickness(0),
            Padding = new Thickness(10, 6, 10, 6)
        };
        Grid.SetRow(inputBox, 1);

        var buttons = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right
        };

        string? result = null;
        var cancelButton = new Button
        {
            Content = "Cancel",
            Padding = new Thickness(12, 6, 12, 6),
            Margin = new Thickness(0, 0, 8, 0)
        };
        cancelButton.Click += (_, _) => dialog.DialogResult = false;

        var okButton = new Button
        {
            Content = "Create",
            Padding = new Thickness(12, 6, 12, 6)
        };
        okButton.Click += (_, _) =>
        {
            result = inputBox.Text;
            dialog.DialogResult = true;
        };

        buttons.Children.Add(cancelButton);
        buttons.Children.Add(okButton);
        Grid.SetRow(buttons, 2);

        layout.Children.Add(messageBlock);
        layout.Children.Add(inputBox);
        layout.Children.Add(buttons);
        dialog.Content = layout;
        inputBox.Focus();
        inputBox.SelectAll();

        return dialog.ShowDialog() == true ? result : null;
    }
}
