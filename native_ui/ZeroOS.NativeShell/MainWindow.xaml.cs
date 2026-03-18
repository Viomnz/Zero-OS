using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Text.Json;
using Microsoft.Win32;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;

namespace ZeroOS.NativeShell;

public partial class MainWindow : Window
{
    private const string RepoUrl = "https://github.com/Viomnz/Zero-OS";
    private const string ReleasesUrl = "https://github.com/Viomnz/Zero-OS/releases";
    private const string CloneCommand = "git clone https://github.com/Viomnz/Zero-OS.git";
    private const string FirstRunCommand = @".\zero_os_launcher.ps1 first-run";
    private const string OpenShellCommand = "Start-Process \".\\zero_os_shell.html\"";
    private const string DownloadNativeAppLink = "https://github.com/Viomnz/Zero-OS/releases";
    private const string PublishCommand = @".\publish.ps1";
    private const string PortableInstallerCommand = @".\package_portable.ps1";
    private const string MsixCommand = @".\package_msix.ps1";
    private readonly string _projectFile;

    private readonly string _repoRoot;
    private readonly string _nativeUiRoot;
    private readonly NativeBackend _backend;
    private readonly NativeDiagnostics _diagnostics;
    private readonly DispatcherTimer _runtimeLoopTimer;
    private readonly ObservableCollection<string> _logs = new();
    private string? _activeWorkspacePath;
    private bool _activeWorkspacePathEditable;
    private bool _workspaceDirty;
    private bool _suspendWorkspaceDirtyTracking;
    private bool _runtimeLoopTickInFlight;
    private bool _autoEnableRuntimeLoopOnLaunch;

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
        _runtimeLoopTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(30) };
        _runtimeLoopTimer.Tick += RuntimeLoopTimer_Tick;
        _autoEnableRuntimeLoopOnLaunch = LoadRuntimeStartupPreference();

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
        RefreshCodeIndexStatus();
        RefreshGithubData();
        RefreshReleaseData();
        RefreshSecuritySpecs();
        RefreshQuickStartStatus();
        RefreshRuntimeContinuityStatus();
        RefreshSystemHealth();
        RefreshAutonomyStatus();
        RefreshControlMapStatus();
        RefreshLocalModsStatus();
        ApplyRuntimeLoopStartupPreference();
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
    private void RunFirstRun_Click(object sender, RoutedEventArgs e) => RunLauncherCommand("first-run", "First-run complete", promptOpenShell: true);
    private void OpenShellUi_Click(object sender, RoutedEventArgs e)
    {
        OpenPath(Path.Combine(_repoRoot, "zero_os_shell.html"));
        SetStatus("Opened Zero OS shell UI.");
        AppendLog("Opened Zero OS shell UI");
    }

    private void OpenRepository_Click(object sender, RoutedEventArgs e) => OpenUrl(RepoUrl);
    private void OpenReleases_Click(object sender, RoutedEventArgs e) => OpenUrl(ReleasesUrl);
    private void QuickStartInstallBackgroundAgent_Click(object sender, RoutedEventArgs e)
    {
        _autoEnableRuntimeLoopOnLaunch = true;
        SaveRuntimeStartupPreference();
        RunBackendTask("zero ai runtime agent install", "Zero AI always-on background agent installed");
        RefreshQuickStartStatus();
    }

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
    private void RefreshSystemHealth_Click(object sender, RoutedEventArgs e)
    {
        RefreshSystemHealth();
        SetStatus("System health refreshed.");
    }

    private void FixSystemHealthNow_Click(object sender, RoutedEventArgs e)
    {
        RunSystemHealthFixNow();
    }

    private void RefreshAutonomy_Click(object sender, RoutedEventArgs e)
    {
        RefreshAutonomyStatus();
        SetStatus("Autonomy refreshed.");
    }

    private void RefreshControlMap_Click(object sender, RoutedEventArgs e)
    {
        RefreshControlMapStatus();
        SetStatus("Control map refreshed.");
    }

    private void RefreshLocalMods_Click(object sender, RoutedEventArgs e)
    {
        RefreshLocalModsStatus();
        SetStatus("Local mods refreshed.");
    }

    private void BrowseLocalModFile_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Title = "Select local Zero OS mod file",
            Filter = "Python files (*.py)|*.py|All files (*.*)|*.*",
            InitialDirectory = Directory.Exists(Path.Combine(_repoRoot, "plugins")) ? Path.Combine(_repoRoot, "plugins") : _repoRoot,
            CheckFileExists = true,
            Multiselect = false
        };

        if (dialog.ShowDialog(this) != true)
        {
            return;
        }

        LocalModPathBox.Text = dialog.FileName;
        if (string.IsNullOrWhiteSpace(LocalModNameBox.Text))
        {
            LocalModNameBox.Text = Path.GetFileNameWithoutExtension(dialog.FileName);
        }
        SetStatus("Selected local mod file.");
        AppendLog($"Selected local mod file {dialog.FileName}");
    }

    private void BrowseLocalModFolder_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFolderDialog
        {
            Title = "Select local Zero OS mod folder",
            InitialDirectory = Directory.Exists(Path.Combine(_repoRoot, "plugins")) ? Path.Combine(_repoRoot, "plugins") : _repoRoot,
            Multiselect = false
        };

        if (dialog.ShowDialog(this) != true)
        {
            return;
        }

        LocalModPathBox.Text = dialog.FolderName;
        if (string.IsNullOrWhiteSpace(LocalModNameBox.Text))
        {
            LocalModNameBox.Text = Path.GetFileName(dialog.FolderName.TrimEnd(Path.DirectorySeparatorChar));
        }
        SetStatus("Selected local mod folder.");
        AppendLog($"Selected local mod folder {dialog.FolderName}");
    }

    private void InstallLocalModPath_Click(object sender, RoutedEventArgs e)
    {
        var path = string.IsNullOrWhiteSpace(LocalModPathBox.Text) ? null : LocalModPathBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(path))
        {
            SetStatus("Enter or browse to a local mod path first.");
            return;
        }

        RunBackendTask($"plugin install local {QuoteCommandArgument(path)}", "Local mod install complete");
    }

    private void ScaffoldLocalMod_Click(object sender, RoutedEventArgs e)
    {
        var proposed = string.IsNullOrWhiteSpace(LocalModNameBox.Text) ? "my_local_mod" : LocalModNameBox.Text.Trim();
        var pluginName = PromptForText("Scaffold Local Mod", "Enter the private-local mod name:", proposed);
        if (string.IsNullOrWhiteSpace(pluginName))
        {
            return;
        }

        LocalModNameBox.Text = pluginName.Trim();
        RunBackendTask($"plugin scaffold {pluginName.Trim()}", "Local mod scaffold complete");
    }

    private void EnableLocalMod_Click(object sender, RoutedEventArgs e)
    {
        var pluginName = SelectedLocalModName();
        if (pluginName == null)
        {
            return;
        }

        RunBackendTask($"plugin enable {pluginName}", "Local mod enabled");
    }

    private void DisableLocalMod_Click(object sender, RoutedEventArgs e)
    {
        var pluginName = SelectedLocalModName();
        if (pluginName == null)
        {
            return;
        }

        RunBackendTask($"plugin disable {pluginName}", "Local mod disabled");
    }

    private void VerifyLocalMod_Click(object sender, RoutedEventArgs e)
    {
        var pluginName = SelectedLocalModName();
        if (pluginName == null)
        {
            return;
        }

        RunBackendTask($"plugin verify {pluginName}", "Local mod verification complete");
    }

    private void SignLocalMod_Click(object sender, RoutedEventArgs e)
    {
        var pluginName = SelectedLocalModName();
        if (pluginName == null)
        {
            return;
        }

        RunBackendTask($"plugin sign {pluginName}", "Local mod signature refreshed");
    }

    private void OpenPluginsFolder_Click(object sender, RoutedEventArgs e)
    {
        var pluginsRoot = Path.Combine(_repoRoot, "plugins");
        Directory.CreateDirectory(pluginsRoot);
        OpenPath(pluginsRoot);
        SetStatus("Opened plugins folder.");
        AppendLog("Opened plugins folder");
    }

    private void CopyPublishCommand_Click(object sender, RoutedEventArgs e) => CopyText(PublishCommand, "publish command");
    private void CopyMsixCommand_Click(object sender, RoutedEventArgs e) => CopyText(MsixCommand, "MSIX command");

    private void BuildNativePublish_Click(object sender, RoutedEventArgs e)
    {
        RunNativeScript("publish.ps1", "Native publish complete");
    }

    private void CreatePortableInstaller_Click(object sender, RoutedEventArgs e)
    {
        RunNativeScript("package_portable.ps1", "Portable installer package complete");
    }

    private void CreateNativeMsix_Click(object sender, RoutedEventArgs e)
    {
        RunNativeScript("package_msix.ps1", "MSIX scaffold complete");
    }

    private void ExportBundle_Click(object sender, RoutedEventArgs e) => RunBackendTask("zero os export bundle", "Export bundle complete");
    private void CreateShareZip_Click(object sender, RoutedEventArgs e) => RunBackendTask("zero os share package", "Share zip complete");
    private void KnowEverything_Click(object sender, RoutedEventArgs e) => RunBackendTask("zero ai know everything", "Zero AI know-everything run complete");
    private void KnowEverythingCompleteAll_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero os complete all", "Zero AI know-everything and complete-all run complete");
    private void ZeroAiSelfInspectRefresh_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai self inspect refresh", "Zero AI self inspect and refresh complete");
    private void ZeroAiSelfRepairRestoreContinuity_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai self repair restore continuity", "Zero AI self repair restore continuity complete");
    private void ZeroAiContinuityPolicyStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity policy status", "Zero AI continuity policy status loaded");
    private void ZeroAiContinuityPolicyAutoStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity policy auto", "Zero AI auto policy recommendation loaded");
    private void ZeroAiContinuityPolicyAutoApply_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity policy auto apply", "Zero AI auto policy selection complete");
    private void ZeroAiContinuityGovernanceStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity governance status", "Zero AI continuity governance status loaded");
    private void ZeroAiContinuityGovernanceAutoStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity governance auto", "Zero AI continuity governance auto recommendation loaded");
    private void ZeroAiContinuityGovernanceAutoApply_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity governance auto apply", "Zero AI continuity governance auto toggle complete");
    private void ZeroAiContinuityGovernanceOn_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity governance on interval=180", "Zero AI continuity governance enabled");
    private void ZeroAiContinuityGovernanceTick_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity governance tick", "Zero AI continuity governance tick complete");
    private void ZeroAiContinuityGovernanceOff_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity governance off", "Zero AI continuity governance disabled");
    private void ZeroAiJobsStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai jobs status", "Zero AI jobs status loaded");
    private void ZeroAiJobsContinuityGovernanceAutoStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai jobs continuity governance auto", "Zero AI jobs governance auto recommendation loaded");
    private void ZeroAiJobsContinuityGovernanceAutoApply_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai jobs continuity governance auto apply", "Zero AI jobs governance auto toggle complete");
    private void ZeroAiJobsContinuityGovernanceOn_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai jobs continuity governance on interval=180", "Zero AI continuity governance scheduled in jobs");
    private void ZeroAiJobsTick_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai jobs tick", "Zero AI jobs tick complete");
    private void ZeroAiJobsContinuityGovernanceOff_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai jobs continuity governance off", "Zero AI continuity governance removed from jobs");
    private void ZeroAiRuntimeStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime status", "Zero AI runtime status loaded");
    private void ZeroAiRuntimeRun_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime run", "Zero AI runtime loop complete");
    private void ZeroAiRuntimeLoopStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime loop status", "Zero AI runtime loop status loaded");
    private void ZeroAiRuntimeLoopOn_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime loop on interval=180", "Zero AI runtime loop enabled");
    private void ZeroAiRuntimeLoopTick_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime loop tick", "Zero AI runtime loop tick complete");
    private void ZeroAiRuntimeLoopOff_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime loop off", "Zero AI runtime loop disabled");
    private void ZeroAiRuntimeAgentInstall_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime agent install", "Zero AI background agent installed");
    private void ZeroAiRuntimeAgentStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime agent status", "Zero AI background agent status loaded");
    private void ZeroAiRuntimeAgentStart_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime agent start", "Zero AI background agent started");
    private void ZeroAiRuntimeAgentStop_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime agent stop", "Zero AI background agent stopped");
    private void ZeroAiRuntimeAgentUninstall_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai runtime agent uninstall", "Zero AI background agent uninstalled");
    private void ZeroAiAutonomySync_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai autonomy sync", "Zero AI autonomy goals synced");
    private void ZeroAiAutonomyRun_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai autonomy run", "Zero AI autonomous work run complete");
    private void ZeroAiAutonomyLoopOn_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai autonomy loop on interval=300", "Zero AI autonomy loop enabled");
    private void ZeroAiAutonomyLoopTick_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai autonomy loop tick", "Zero AI autonomy loop tick complete");
    private void ZeroAiAutonomyLoopOff_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai autonomy loop off", "Zero AI autonomy loop disabled");
    private void ZeroAiEvolutionStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai evolution status", "Zero AI bounded evolution status loaded");
    private void ZeroAiEvolutionAutoRun_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai evolution auto run", "Zero AI bounded self evolution run complete");
    private void ZeroAiEvolutionRollback_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai evolution rollback", "Zero AI bounded evolution rollback complete");
    private void ZeroAiSourceEvolutionStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai source evolution status", "Zero AI source evolution status loaded");
    private void ZeroAiSourceEvolutionAutoRun_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai source evolution auto run", "Zero AI guarded source evolution run complete");
    private void ZeroAiSourceEvolutionRollback_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai source evolution rollback", "Zero AI guarded source evolution rollback complete");
    private void ZeroAiNext_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai next", "Zero AI highest-value control map loaded");
    private void ZeroAiToolsStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai tools status", "Zero AI tool registry loaded");
    private void ZeroAiCapabilityMapStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai capability map status", "Zero AI capability map loaded");
    private void ZeroAiControlWorkflowsStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai control workflows status", "Zero AI control workflows status loaded");
    private void ZeroAiBenchmarkDashboardRefresh_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai benchmark dashboard refresh", "Zero AI benchmark dashboard refreshed");
    private void ZeroAiBenchmarkAlertsRefresh_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai benchmark alerts refresh", "Zero AI benchmark alert routes refreshed");
    private void ZeroAiBenchmarkRemediationRefresh_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai benchmark remediation refresh", "Zero AI benchmark remediation refreshed");
    private void ZeroAiBenchmarkRemediationRequest_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai benchmark remediation request", "Zero AI benchmark remediation approval requested");
    private void ZeroAiBenchmarkRemediationApprove_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai benchmark remediation approve", "Zero AI benchmark remediation approved");
    private void ZeroAiBenchmarkRemediationReject_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai benchmark remediation reject", "Zero AI benchmark remediation rejected");
    private void ZeroAiBenchmarkRemediationExecute_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai benchmark remediation execute", "Zero AI benchmark remediation execution attempted");
    private void RememberRuntimeLoopOnLaunch_Click(object sender, RoutedEventArgs e)
        => SetRuntimeLoopStartupPreference(true);
    private void ForgetRuntimeLoopOnLaunch_Click(object sender, RoutedEventArgs e)
        => SetRuntimeLoopStartupPreference(false);
    private void ZeroAiContinuityPolicyStrict_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity policy set strict", "Zero AI continuity policy set to strict");
    private void ZeroAiContinuityPolicyBalanced_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity policy set balanced", "Zero AI continuity policy set to balanced");
    private void ZeroAiContinuityPolicyResearch_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity policy set research", "Zero AI continuity policy set to research");
    private void ZeroAiContinuityCheckpointStatus_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity checkpoint status", "Zero AI continuity checkpoint status loaded");
    private void ZeroAiContinuityRestoreLastSafe_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity restore last safe", "Zero AI last safe continuity restored");
    private void ZeroAiContinuityGovernorCheck_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity governor check", "Zero AI continuity governor safety check complete");
    private void ZeroAiContinuityGovernorApply_Click(object sender, RoutedEventArgs e)
        => RunBackendTask("zero ai continuity governor apply", "Zero AI continuity governor apply complete");
    private void ZeroAiContinuitySimulate_Click(object sender, RoutedEventArgs e)
        => RunContinuitySimulationTask(apply: false);
    private void ZeroAiContinuitySimulateApply_Click(object sender, RoutedEventArgs e)
        => RunContinuitySimulationTask(apply: true);
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

    private void OpenNativeInstallerFolder_Click(object sender, RoutedEventArgs e)
    {
        OpenPath(Path.Combine(_nativeUiRoot, "installers"));
        SetStatus("Opened native installer folder.");
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

    private void IndexWorkspace_Click(object sender, RoutedEventArgs e)
    {
        RunCodeIndexTask("zero ai index workspace max=50000 shard=1000 incremental=true", "Workspace index refreshed.");
    }

    private void RefreshCodeIndex_Click(object sender, RoutedEventArgs e)
    {
        RefreshCodeIndexStatus();
        SetStatus("Code index status refreshed.");
    }

    private void WatchCodeIndexOn_Click(object sender, RoutedEventArgs e)
    {
        RunCodeIndexTask("zero ai index watch on name=main interval=30", "Code index watcher enabled.");
    }

    private void WatchCodeIndexTick_Click(object sender, RoutedEventArgs e)
    {
        RunCodeIndexTask("zero ai index watch tick name=main max=50000 shard=1000", "Code index watcher tick complete.");
    }

    private void WatchCodeIndexStatus_Click(object sender, RoutedEventArgs e)
    {
        RefreshCodeIndexStatus();
        SetStatus("Code index watcher status refreshed.");
    }

    private void WatchCodeIndexOff_Click(object sender, RoutedEventArgs e)
    {
        RunCodeIndexTask("zero ai index watch off name=main", "Code index watcher disabled.");
    }

    private void SearchCodeIndex_Click(object sender, RoutedEventArgs e)
    {
        var query = string.IsNullOrWhiteSpace(CodeSearchBox.Text) ? "native shell" : CodeSearchBox.Text.Trim();
        RunCodeIndexTask($"zero ai code search {query} limit=10", "Code search complete.");
    }

    private void SearchSymbols_Click(object sender, RoutedEventArgs e)
    {
        var query = string.IsNullOrWhiteSpace(CodeSearchBox.Text) ? "launch" : CodeSearchBox.Text.Trim();
        RunCodeIndexTask($"zero ai symbol search {query} limit=10", "Symbol search complete.");
    }

    private void RefreshQuickStart_Click(object sender, RoutedEventArgs e)
    {
        RefreshQuickStartStatus();
        SetStatus("Quick start status refreshed.");
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
        if (ShouldRefreshRuntimeContinuityStatus(command))
        {
            RefreshRuntimeContinuityStatus();
            RefreshSystemHealth();
            RefreshQuickStartStatus();
            RefreshAutonomyStatus();
            RefreshControlMapStatus();
        }
        else if (command.Trim().StartsWith("zero ai autonomy", StringComparison.OrdinalIgnoreCase))
        {
            RefreshAutonomyStatus();
            RefreshControlMapStatus();
        }
        else if (command.Trim().StartsWith("zero ai source evolution", StringComparison.OrdinalIgnoreCase))
        {
            RefreshAutonomyStatus();
            RefreshControlMapStatus();
        }
        else if (ShouldRefreshControlMapStatus(command))
        {
            RefreshControlMapStatus();
        }

        if (ShouldRefreshLocalModsStatus(command))
        {
            RefreshLocalModsStatus();
        }
    }

    private void RunContinuitySimulationTask(bool apply)
    {
        var stagedPatch = SelectAndStageContinuityProposal();
        if (string.IsNullOrWhiteSpace(stagedPatch))
        {
            SetStatus(apply ? "Continuity simulated apply canceled." : "Continuity simulation canceled.");
            AppendLog("Continuity proposal selection canceled");
            return;
        }

        var command = apply
            ? $"zero ai continuity simulate apply patch={stagedPatch}"
            : $"zero ai continuity simulate patch={stagedPatch}";
        var successMessage = apply
            ? "Zero AI safe simulated update apply complete"
            : "Zero AI continuity simulation complete";

        RunBackendTask(command, successMessage);
    }

    private string? SelectAndStageContinuityProposal()
    {
        var dialog = new OpenFileDialog
        {
            Title = "Select Zero AI continuity proposal JSON",
            Filter = "JSON files (*.json)|*.json|All files (*.*)|*.*",
            InitialDirectory = _repoRoot,
            CheckFileExists = true,
            Multiselect = false
        };

        if (dialog.ShowDialog(this) != true)
        {
            return null;
        }

        var sourcePath = dialog.FileName;
        try
        {
            var proposalsRoot = Path.Combine(_repoRoot, ".zero_os", "runtime", "proposals");
            Directory.CreateDirectory(proposalsRoot);

            var safeBaseName = Path.GetFileNameWithoutExtension(sourcePath);
            foreach (var invalid in Path.GetInvalidFileNameChars())
            {
                safeBaseName = safeBaseName.Replace(invalid, '_');
            }

            safeBaseName = string.IsNullOrWhiteSpace(safeBaseName) ? "proposal" : safeBaseName.Replace(' ', '_');
            var stagedFileName = $"{safeBaseName}_{DateTime.UtcNow:yyyyMMddTHHmmssZ}.json";
            var stagedPath = Path.Combine(proposalsRoot, stagedFileName);
            File.Copy(sourcePath, stagedPath, overwrite: true);

            var relativePath = Path.GetRelativePath(_repoRoot, stagedPath).Replace("\\", "/");
            AppendLog($"Staged continuity proposal {relativePath}");
            return relativePath;
        }
        catch (Exception ex)
        {
            SetStatus($"Failed to stage proposal: {ex.Message}");
            AppendLog($"Failed to stage continuity proposal: {ex.Message}");
            return null;
        }
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

    private void RunLauncherCommand(string launcherArgs, string successMessage, bool promptOpenShell = false)
    {
        var launcherPath = Path.Combine(_repoRoot, "zero_os_launcher.ps1");
        if (!File.Exists(launcherPath))
        {
            SetStatus("Launcher script is missing.");
            AppendLog("Launcher script missing");
            return;
        }

        SetStatus($"Running launcher: {launcherArgs}");
        AppendLog($"Running launcher command: {launcherArgs}");

        var psi = new ProcessStartInfo
        {
            FileName = "powershell",
            Arguments = $"-NoProfile -ExecutionPolicy Bypass -File \"{launcherPath}\" {launcherArgs}",
            WorkingDirectory = _repoRoot,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        using var process = Process.Start(psi);
        if (process == null)
        {
            SetStatus("Failed to start launcher.");
            AppendLog("Failed to start launcher");
            return;
        }

        var stdout = process.StandardOutput.ReadToEnd();
        var stderr = process.StandardError.ReadToEnd();
        process.WaitForExit();

        OutputBox.Text = string.IsNullOrWhiteSpace(stderr) ? stdout : $"{stdout}{Environment.NewLine}{stderr}".Trim();
        if (process.ExitCode == 0)
        {
            SetStatus(successMessage);
            AppendLog(successMessage);
            if (promptOpenShell)
            {
                var result = MessageBox.Show(
                    "First-run finished. Open the Zero OS shell UI now?",
                    "Open Shell UI",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Question
                );
                if (result == MessageBoxResult.Yes)
                {
                    OpenShellUi_Click(this, new RoutedEventArgs());
                }
            }
        }
        else
        {
            SetStatus("Launcher completed with errors.");
            AppendLog($"Launcher failed: {launcherArgs}");
        }

        RefreshQuickStartStatus();
    }

    private void RefreshQuickStartStatus()
    {
        var shellPath = Path.Combine(_repoRoot, "zero_os_shell.html");
        var runtimeRoot = Path.Combine(_repoRoot, ".zero_os", "runtime");
        var knowledgeIndex = Path.Combine(runtimeRoot, "zero_ai_knowledge_index.json");
        var brainAwareness = Path.Combine(runtimeRoot, "zero_ai_brain_awareness.json");
        var gapStatus = Path.Combine(runtimeRoot, "zero_ai_gap_status.json");
        var installerDir = Path.Combine(_nativeUiRoot, "installers");
        var msixDir = Path.Combine(_nativeUiRoot, "msix");
        var portableReady = Directory.Exists(installerDir) && Directory.GetFiles(installerDir, "*.zip").Length > 0;
        var msixReady = Directory.Exists(msixDir) && Directory.GetFiles(msixDir, "*.msix").Length > 0;
        var runtimeStatus = _backend.RunTask("zero ai runtime status");
        var runtimeAgentInstalled = false;
        var runtimeAgentRunning = false;
        if (runtimeStatus.Payload.HasValue && runtimeStatus.Payload.Value.ValueKind == JsonValueKind.Object)
        {
            var payload = runtimeStatus.Payload.Value;
            if (payload.TryGetProperty("runtime_agent", out var runtimeAgent))
            {
                runtimeAgentInstalled = ReadBool(runtimeAgent, "installed");
                runtimeAgentRunning = ReadBool(runtimeAgent, "running");
            }
        }

        var lines = new List<string>
        {
            "Quick Start Wizard",
            "",
            "Fastest path: Download Native App -> Run First-Run -> Open Shell UI",
            "",
            $"1. Repository available: {(Directory.Exists(_repoRoot) ? "yes" : "no")}",
            $"2. Launcher available: {(File.Exists(Path.Combine(_repoRoot, "zero_os_launcher.ps1")) ? "yes" : "no")}",
            $"3. Shell UI file available: {(File.Exists(shellPath) ? "yes" : "no")}",
            $"4. Runtime folder created: {(Directory.Exists(runtimeRoot) ? "yes" : "no")}",
            $"5. Knowledge index built: {(File.Exists(knowledgeIndex) ? "yes" : "no")}",
            $"6. Brain awareness built: {(File.Exists(brainAwareness) ? "yes" : "no")}",
            $"7. Gap status report: {(File.Exists(gapStatus) ? "yes" : "no")}",
            $"8. Portable installer ready: {(portableReady ? "yes" : "no")}",
            $"9. MSIX package ready: {(msixReady ? "yes" : "no")}",
            $"10. Background agent installed: {(runtimeAgentInstalled ? "yes" : "no")}",
            $"11. Background agent running: {(runtimeAgentRunning ? "yes" : "no")}",
            $"12. Auto-enable runtime loop on launch: {(_autoEnableRuntimeLoopOnLaunch ? "yes" : "no")}",
            "",
            "Recommended order:",
            "Download Native App",
            "Step 1. Open Repository",
            "Step 2. Run First-Run",
            "Step 3. Open Shell UI",
            "Step 4. Install + Start Background Agent",
            "Step 5. Know Everything",
            "Step 6. Complete All"
        };

        QuickStartStatusBox.Text = string.Join(Environment.NewLine, lines);
    }

    private void RefreshSystemHealth()
    {
        var runtimeStatus = _backend.RunTask("zero ai runtime status");
        var continuityStatus = _backend.RunTask("zero ai self continuity status");
        SystemHealthBox.Text = BuildSystemHealthSummary(runtimeStatus, continuityStatus);
    }

    private void RefreshAutonomyStatus()
    {
        var result = _backend.RunTask("zero ai autonomy status");
        AutonomyBox.Text = BuildAutonomySummary(result);
    }

    private void RefreshControlMapStatus()
    {
        var controllerResult = _backend.RunTask("zero ai controller registry status");
        var toolResult = _backend.RunTask("zero ai tools status");
        var capabilityResult = _backend.RunTask("zero ai capability map status");
        var benchmarkDashboardResult = _backend.RunTask("zero ai benchmark dashboard status");
        var benchmarkAlertsResult = _backend.RunTask("zero ai benchmark alerts status");
        var benchmarkRemediationResult = _backend.RunTask("zero ai benchmark remediation status");
        ControlMapBox.Text = BuildControlMapSummary(controllerResult, toolResult, capabilityResult, benchmarkDashboardResult, benchmarkAlertsResult, benchmarkRemediationResult);
    }

    private void RefreshLocalModsStatus()
    {
        var result = _backend.RunTask("plugin status");
        LocalModsBox.Text = BuildLocalModsSummary(result);
    }

    private void RefreshRuntimeContinuityStatus()
    {
        var result = _backend.RunTask("zero ai runtime status");
        RuntimeContinuityBox.Text = BuildRuntimeContinuitySummary(result)
            + Environment.NewLine + Environment.NewLine
            + $"Auto-enable runtime loop on launch: {(_autoEnableRuntimeLoopOnLaunch ? "yes" : "no")}";
        SyncRuntimeLoopTimer(result);
    }

    private string RuntimeShellSettingsPath()
    {
        return Path.Combine(_repoRoot, ".zero_os", "native_shell", "ui_settings.json");
    }

    private bool LoadRuntimeStartupPreference()
    {
        var path = RuntimeShellSettingsPath();
        try
        {
            if (!File.Exists(path))
            {
                return false;
            }

            using var document = JsonDocument.Parse(File.ReadAllText(path));
            if (document.RootElement.ValueKind == JsonValueKind.Object
                && document.RootElement.TryGetProperty("auto_enable_runtime_loop_on_launch", out var setting)
                && (setting.ValueKind == JsonValueKind.True || setting.ValueKind == JsonValueKind.False))
            {
                return setting.GetBoolean();
            }
        }
        catch (Exception ex)
        {
            AppendLog($"Failed to load runtime startup preference: {ex.Message}");
        }

        return false;
    }

    private void SaveRuntimeStartupPreference()
    {
        var path = RuntimeShellSettingsPath();
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var payload = new Dictionary<string, object>
        {
            ["auto_enable_runtime_loop_on_launch"] = _autoEnableRuntimeLoopOnLaunch,
            ["updated_utc"] = DateTime.UtcNow.ToString("O"),
        };
        File.WriteAllText(path, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
    }

    private void SetRuntimeLoopStartupPreference(bool enabled)
    {
        _autoEnableRuntimeLoopOnLaunch = enabled;
        SaveRuntimeStartupPreference();
        RefreshRuntimeContinuityStatus();
        RefreshAutonomyStatus();
        RefreshControlMapStatus();
        SetStatus(enabled ? "Runtime loop will auto-enable on launch." : "Runtime loop will no longer auto-enable on launch.");
        AppendLog(enabled ? "Enabled runtime loop auto-start on launch" : "Disabled runtime loop auto-start on launch");
    }

    private void ApplyRuntimeLoopStartupPreference()
    {
        if (!_autoEnableRuntimeLoopOnLaunch)
        {
            return;
        }

        var status = _backend.RunTask("zero ai runtime loop status");
        if (status.Payload.HasValue
            && status.Payload.Value.ValueKind == JsonValueKind.Object
            && ReadBool(status.Payload.Value, "enabled"))
        {
            return;
        }

        AppendLog("Auto-enabling Zero AI runtime loop on launch");
        var enabled = _backend.RunTask("zero ai runtime loop on interval=180");
        if (enabled.Ok)
        {
            SetStatus("Auto-enabled Zero AI runtime loop on launch.");
        }
        else
        {
            SetStatus("Tried to auto-enable runtime loop. Review output.");
        }
        RefreshRuntimeContinuityStatus();
        RefreshAutonomyStatus();
        RefreshControlMapStatus();
    }

    private static bool ShouldRefreshRuntimeContinuityStatus(string command)
    {
        var normalized = command.Trim().ToLowerInvariant();
        return normalized.StartsWith("zero ai runtime", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai continuity", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai jobs continuity governance", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai source evolution", StringComparison.Ordinal)
            || normalized == "zero ai jobs tick"
            || normalized == "zero ai self inspect refresh"
            || normalized == "zero ai self repair restore continuity"
            || normalized == "zero ai know everything"
            || normalized == "zero os complete all";
    }

    private static bool ShouldRefreshControlMapStatus(string command)
    {
        var normalized = command.Trim().ToLowerInvariant();
        return normalized == "zero ai next"
            || normalized.StartsWith("zero ai controller registry", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai tools", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai capability map", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai benchmark", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai control workflows", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai autonomy", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai runtime", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai source evolution", StringComparison.Ordinal)
            || normalized.StartsWith("zero ai workflow", StringComparison.Ordinal)
              || normalized == "zero ai self inspect refresh"
              || normalized == "zero ai self repair restore continuity"
              || normalized == "zero ai know everything"
              || normalized == "zero os complete all";
    }

    private static bool ShouldRefreshLocalModsStatus(string command)
    {
        return command.Trim().StartsWith("plugin ", StringComparison.OrdinalIgnoreCase);
    }

    private static string BuildRuntimeContinuitySummary(NativeCommandResult result)
    {
        if (!result.Payload.HasValue || result.Payload.Value.ValueKind != JsonValueKind.Object)
        {
            return "Runtime Continuity Background" + Environment.NewLine + Environment.NewLine + result.DisplayText();
        }

        var payload = result.Payload.Value;
        payload.TryGetProperty("runtime_loop", out var runtimeLoop);
        payload.TryGetProperty("runtime_agent", out var runtimeAgent);
        payload.TryGetProperty("autonomy", out var autonomy);
        payload.TryGetProperty("autonomy_background", out var autonomyBackground);
        payload.TryGetProperty("source_evolution", out var sourceEvolution);
        if (TryGetBool(payload, "missing", out var missing) && missing)
        {
            return string.Join(
                Environment.NewLine,
                "Runtime Continuity Background",
                "",
                "No runtime status has been captured yet.",
                "Run `Zero AI Runtime Run` to build the live background continuity report.",
                "",
                $"Runtime loop enabled: {(ReadBool(runtimeLoop, "enabled") ? "yes" : "no")}",
                $"Runtime loop interval: {ReadNumber(runtimeLoop, "interval_seconds")} seconds",
                $"Background agent running: {(ReadBool(runtimeAgent, "running") ? "yes" : "no")}"
            );
        }

        if (!payload.TryGetProperty("continuity_governance_background", out var background) || background.ValueKind != JsonValueKind.Object)
        {
            return "Runtime Continuity Background" + Environment.NewLine + Environment.NewLine + result.DisplayText();
        }

        payload.TryGetProperty("capability_control_map", out var capabilityMap);
        background.TryGetProperty("auto", out var auto);
        background.TryGetProperty("continuity_governance", out var governance);
        background.TryGetProperty("jobs", out var jobs);
        background.TryGetProperty("tick", out var tick);

        var lines = new List<string>
        {
            "Runtime Continuity Background",
            "",
            $"Runtime ready: {ReadBool(payload, "runtime_ready")}",
            $"Runtime score: {ReadNumber(payload, "runtime_score")}",
            $"Last runtime status: {ReadString(payload, "time_utc")}",
            "",
            $"Runtime loop enabled: {(ReadBool(runtimeLoop, "enabled") ? "yes" : "no")}",
            $"Runtime loop interval: {ReadNumber(runtimeLoop, "interval_seconds")} seconds",
            $"Runtime loop due now: {(ReadBool(runtimeLoop, "due_now") ? "yes" : "no")}",
            $"Runtime loop last run: {ReadString(runtimeLoop, "last_run_utc")}",
            $"Runtime loop next run: {ReadString(runtimeLoop, "next_run_utc")}",
            $"Runtime loop failures: {ReadNumber(runtimeLoop, "consecutive_failures")}",
            $"Runtime loop backoff: {ReadNumber(runtimeLoop, "backoff_seconds")} seconds",
            $"Runtime loop last failure: {ReadString(runtimeLoop, "last_failure")}",
            "",
            $"Background agent installed: {(ReadBool(runtimeAgent, "installed") ? "yes" : "no")}",
            $"Background agent running: {(ReadBool(runtimeAgent, "running") ? "yes" : "no")}",
            $"Background agent auto-start on login: {(ReadBool(runtimeAgent, "auto_start_on_login") ? "yes" : "no")}",
            $"Background agent pid: {ReadString(runtimeAgent, "worker_pid")}",
            $"Background agent heartbeat: {ReadString(runtimeAgent, "last_heartbeat_utc")}",
            $"Background agent heartbeat fresh: {(ReadBool(runtimeAgent, "heartbeat_fresh") ? "yes" : "no")}",
            $"Background agent last tick: {ReadString(runtimeAgent, "last_tick_utc")}",
            $"Background agent last failure: {ReadString(runtimeAgent, "last_failure")}",
            $"Background agent launcher: {ReadString(runtimeAgent, "startup_launcher_path")}",
            "",
            $"Auto recommendation: {(ReadBool(auto, "recommended_enabled") ? "keep on" : "keep off")}",
            $"Recommended interval: {ReadNumber(auto, "recommended_interval_seconds")} seconds",
            $"Current governance state: {(ReadBool(governance, "enabled") ? "on" : "off")}",
            $"Current policy level: {ReadString(governance, "current_policy_level")}",
            $"Jobs recurring count: {ReadNumber(jobs, "recurring_count")}",
            "",
            $"Background tick executed: {(ReadBool(tick, "ticked") ? "yes" : "no")}",
            $"Tick reason: {ReadString(tick, "reason")}",
            $"Tick result ok: {ReadNestedBool(tick, "result", "ok")}",
            $"Last governance tick: {ReadString(governance, "last_tick_utc")}",
            $"Last governance actions: {ReadStringArray(governance, "last_actions")}",
            "",
            $"Auto reasons: {ReadStringArray(auto, "reasons")}",
            "",
            $"Autonomy current goal: {ReadString(autonomy, "current_goal_title")}",
            $"Autonomy loop enabled: {(ReadNestedBool(autonomy, "loop", "enabled") ? "yes" : "no")}",
            $"Autonomy background ran: {(ReadBool(autonomyBackground, "ran") ? "yes" : "no")}",
            $"Autonomy background reason: {ReadString(autonomyBackground, "reason")}",
            "",
            $"Source evolution ready: {(ReadBool(sourceEvolution, "source_evolution_ready") ? "yes" : "no")}",
            $"Source evolution due now: {(ReadBool(sourceEvolution, "due_now") ? "yes" : "no")}",
            $"Source evolution action: {ReadString(sourceEvolution, "recommended_action")}",
            $"Source evolution review: {ReadNestedString(sourceEvolution, "proposal", "patch_review_summary")}",
            $"Source evolution changes: {ReadNestedStringArray(sourceEvolution, "proposal", "patch_review_headlines")}"
        };

        if (capabilityMap.ValueKind == JsonValueKind.Object)
        {
            lines.Add("");
            lines.Add("Capability control map:");
            lines.Add($"Autonomous surface: {ReadNestedNumber(capabilityMap, "summary", "autonomous_surface_score")}%");
            lines.Add($"Active autonomous surface: {ReadNestedNumber(capabilityMap, "summary", "active_autonomous_surface_score")}%");
            lines.Add($"Approval-gated count: {ReadNestedNumber(capabilityMap, "summary", "approval_gated_count")}");
            lines.Add($"Forbidden count: {ReadNestedNumber(capabilityMap, "summary", "forbidden_count")}");
            lines.Add($"Fully autonomous control: {(ReadBool(capabilityMap, "fully_autonomous_control") ? "yes" : "no")}");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string BuildAutonomySummary(NativeCommandResult result)
    {
        if (!result.Payload.HasValue || result.Payload.Value.ValueKind != JsonValueKind.Object)
        {
            return "Autonomy" + Environment.NewLine + Environment.NewLine + result.DisplayText();
        }

        var payload = result.Payload.Value;
        payload.TryGetProperty("loop", out var loop);
        payload.TryGetProperty("current_goal", out var currentGoal);
        payload.TryGetProperty("recent_runs", out var recentRuns);
        payload.TryGetProperty("evolution", out var evolution);
        payload.TryGetProperty("source_evolution", out var sourceEvolution);
        payload.TryGetProperty("capability_control_map", out var capabilityMap);

        var lines = new List<string>
        {
            "Autonomy",
            "",
            $"Autonomy ready: {(ReadBool(payload, "autonomy_ready") ? "yes" : "no")}",
            $"Open goals: {ReadNumber(payload, "open_count")}",
            $"Blocked goals: {ReadNumber(payload, "blocked_count")}",
            $"Resolved goals: {ReadNumber(payload, "resolved_count")}",
            $"Pending approvals: {ReadNumber(payload, "approvals_pending")}",
            $"Pending jobs: {ReadNumber(payload, "jobs_pending")}",
            "",
            $"Current goal: {ReadString(payload, "current_goal_title")}",
            $"Next action: {ReadString(payload, "current_goal_next_action")}",
            $"Blocked reason: {ReadString(payload, "blocked_reason")}",
            "",
            $"Autonomy loop enabled: {(ReadBool(loop, "enabled") ? "yes" : "no")}",
            $"Autonomy loop due now: {(ReadBool(loop, "due_now") ? "yes" : "no")}",
            $"Autonomy loop interval: {ReadNumber(loop, "interval_seconds")} seconds",
            $"Autonomy loop last run: {ReadString(loop, "last_run_utc")}",
            $"Autonomy loop next run: {ReadString(loop, "next_run_utc")}",
            $"Autonomy loop last goal: {ReadString(loop, "last_goal_title")}",
            $"Autonomy loop last failure: {ReadString(loop, "last_failure")}",
        };

        if (evolution.ValueKind == JsonValueKind.Object)
        {
            evolution.TryGetProperty("pending_candidate", out var pendingCandidate);
            lines.Add("");
            lines.Add("Bounded self evolution:");
            lines.Add($"- Ready: {(ReadBool(payload, "evolution_ready") ? "yes" : "no")}");
            lines.Add($"- Due now: {(ReadBool(payload, "evolution_due_now") ? "yes" : "no")}");
            lines.Add($"- Recommended action: {ReadString(evolution, "recommended_action")}");
            lines.Add($"- Generation: {ReadNumber(evolution, "current_generation")}");
            lines.Add($"- Promotions: {ReadNumber(evolution, "promoted_count")}");
            lines.Add($"- Rollbacks: {ReadNumber(evolution, "rollback_count")}");
            lines.Add($"- Runtime loop target: {ReadNestedNumber(evolution, "current_profile", "runtime_loop_interval_seconds")} seconds");
            lines.Add($"- Autonomy loop target: {ReadNestedNumber(evolution, "current_profile", "autonomy_loop_interval_seconds")} seconds");
            lines.Add($"- Fitness score: {ReadNestedNumber(evolution, "fitness", "fitness_score")}");
            lines.Add($"- Candidate gain: {ReadNestedNumber(evolution, "proposal", "predicted_gain")}");
            lines.Add($"- Pending candidate: {ReadString(pendingCandidate, "candidate_id")}");
        }

        if (sourceEvolution.ValueKind == JsonValueKind.Object)
        {
            sourceEvolution.TryGetProperty("pending_candidate", out var pendingSourceCandidate);
            lines.Add("");
            lines.Add("Guarded source evolution:");
            lines.Add($"- Ready: {(ReadBool(payload, "source_evolution_ready") ? "yes" : "no")}");
            lines.Add($"- Due now: {(ReadBool(payload, "source_evolution_due_now") ? "yes" : "no")}");
            lines.Add($"- Recommended action: {ReadString(sourceEvolution, "recommended_action")}");
            lines.Add($"- Source generation: {ReadNumber(sourceEvolution, "current_source_generation")}");
            lines.Add($"- Promotions: {ReadNumber(sourceEvolution, "promoted_count")}");
            lines.Add($"- Rollbacks: {ReadNumber(sourceEvolution, "rollback_count")}");
            lines.Add($"- Candidate gain: {ReadNestedNumber(sourceEvolution, "proposal", "predicted_gain")}");
            lines.Add($"- Review summary: {ReadNestedString(sourceEvolution, "proposal", "patch_review_summary")}");
            lines.Add($"- Review changes: {ReadNestedStringArray(sourceEvolution, "proposal", "patch_review_headlines")}");
            lines.Add($"- Review artifact: {ReadNestedString(sourceEvolution, "proposal", "patch_review_path")}");
            lines.Add($"- Pending candidate: {ReadString(pendingSourceCandidate, "candidate_id")}");
        }

        if (capabilityMap.ValueKind == JsonValueKind.Object)
        {
            lines.Add("");
            lines.Add("Capability control:");
            lines.Add($"- Autonomous surface: {ReadNestedNumber(capabilityMap, "summary", "autonomous_surface_score")}%");
            lines.Add($"- Active autonomous surface: {ReadNestedNumber(capabilityMap, "summary", "active_autonomous_surface_score")}%");
            lines.Add($"- Approval-gated count: {ReadNestedNumber(capabilityMap, "summary", "approval_gated_count")}");
            lines.Add($"- Forbidden count: {ReadNestedNumber(capabilityMap, "summary", "forbidden_count")}");
            lines.Add($"- Fully autonomous control: {(ReadBool(capabilityMap, "fully_autonomous_control") ? "yes" : "no")}");
        }

        if (currentGoal.ValueKind == JsonValueKind.Object)
        {
            lines.Add("");
            lines.Add("Selected goal details:");
            lines.Add($"- Title: {ReadString(currentGoal, "title")}");
            lines.Add($"- Source: {ReadString(currentGoal, "source")}");
            lines.Add($"- Priority: {ReadNumber(currentGoal, "priority")}");
            lines.Add($"- State: {ReadString(currentGoal, "state")}");
            lines.Add($"- Risk: {ReadString(currentGoal, "risk")}");
            lines.Add($"- Action kind: {ReadString(currentGoal, "action_kind")}");
        }

        if (recentRuns.ValueKind == JsonValueKind.Array && recentRuns.GetArrayLength() > 0)
        {
            lines.Add("");
            lines.Add("Recent autonomous runs:");
            foreach (var item in recentRuns.EnumerateArray().Take(4))
            {
                var title = ReadString(item, "goal_title");
                var summary = FirstNonEmpty(ReadString(item, "summary"), ReadString(item, "reason"), "n/a");
                var ok = ReadBool(item, "ok") ? "ok" : "review";
                lines.Add($"- [{ok}] {title}: {summary}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string BuildControlMapSummary(
        NativeCommandResult controllerResult,
        NativeCommandResult toolResult,
        NativeCommandResult capabilityResult,
        NativeCommandResult benchmarkDashboardResult,
        NativeCommandResult benchmarkAlertsResult,
        NativeCommandResult benchmarkRemediationResult)
    {
        var lines = new List<string>
        {
            "Zero AI Control Map",
            ""
        };

        if (controllerResult.Payload.HasValue && controllerResult.Payload.Value.ValueKind == JsonValueKind.Object)
        {
            var controller = controllerResult.Payload.Value;
            lines.Add("Controller registry:");
            lines.Add($"- Subsystems: {ReadNestedNumber(controller, "summary", "subsystem_count")}");
            lines.Add($"- Active subsystems: {ReadNestedNumber(controller, "summary", "active_subsystem_count")}");
            lines.Add($"- Missing functions: {ReadNestedNumber(controller, "summary", "missing_function_count")}");
            lines.Add($"- Missing tools: {ReadNestedNumber(controller, "tool_summary", "missing_tool_count")}");
            lines.Add("");
            lines.Add("Next priorities:");
            if (controller.TryGetProperty("next_priority", out var nextPriority) && nextPriority.ValueKind == JsonValueKind.Array && nextPriority.GetArrayLength() > 0)
            {
                var index = 1;
                foreach (var item in nextPriority.EnumerateArray().Take(3))
                {
                    lines.Add($"{index}. {item}");
                    index++;
                }
            }
            else
            {
                lines.Add("1. Run `zero ai next` to generate the current highest-value action list.");
            }

            if (controller.TryGetProperty("subsystems", out var subsystems) && subsystems.ValueKind == JsonValueKind.Array)
            {
                lines.Add("");
                lines.Add("Subsystem contracts:");
                foreach (var subsystem in subsystems.EnumerateArray().Take(6))
                {
                    lines.Add($"- {ReadString(subsystem, "label")} [{ReadString(subsystem, "control_level")} / {ReadString(subsystem, "contract_state")}]");
                    lines.Add($"  Missing: {ReadStringArray(subsystem, "missing_functions")}");
                    lines.Add($"  Step: {ReadString(subsystem, "highest_value_step")}");
                    lines.Add($"  Commands: {ReadArrayPreview(subsystem, "commands", 2)}");
                }
            }
        }
        else
        {
            lines.Add("Controller registry:");
            lines.Add(controllerResult.DisplayText());
        }

        lines.Add("");
        if (toolResult.Payload.HasValue && toolResult.Payload.Value.ValueKind == JsonValueKind.Object)
        {
            var tools = toolResult.Payload.Value;
            lines.Add("Tool registry:");
            lines.Add($"- Tool count: {ReadNestedNumber(tools, "summary", "tool_count")}");
            lines.Add($"- Active tools: {ReadNestedNumber(tools, "summary", "active_count")}");
            lines.Add($"- Missing tools: {ReadNestedNumber(tools, "summary", "missing_tool_count")}");
            if (tools.TryGetProperty("missing_tools", out var missingTools) && missingTools.ValueKind == JsonValueKind.Array && missingTools.GetArrayLength() > 0)
            {
                foreach (var item in missingTools.EnumerateArray().Take(4))
                {
                    lines.Add($"  - {ReadString(item, "tool")}: {ReadStringArray(item, "gaps")}");
                }
            }
        }
        else
        {
            lines.Add("Tool registry:");
            lines.Add(toolResult.DisplayText());
        }

        lines.Add("");
        if (capabilityResult.Payload.HasValue && capabilityResult.Payload.Value.ValueKind == JsonValueKind.Object)
        {
            var capability = capabilityResult.Payload.Value;
            lines.Add("Capability surface:");
            lines.Add($"- Autonomous surface: {ReadNestedNumber(capability, "summary", "autonomous_surface_score")}%");
            lines.Add($"- Active autonomous surface: {ReadNestedNumber(capability, "summary", "active_autonomous_surface_score")}%");
            lines.Add($"- Approval-gated count: {ReadNestedNumber(capability, "summary", "approval_gated_count")}");
            lines.Add($"- Forbidden count: {ReadNestedNumber(capability, "summary", "forbidden_count")}");
            lines.Add($"- Highest-value steps: {ReadArrayPreview(capability, "highest_value_steps", 2)}");
        }
        else
        {
            lines.Add("Capability surface:");
            lines.Add(capabilityResult.DisplayText());
        }

        lines.Add("");
        if (benchmarkDashboardResult.Payload.HasValue && benchmarkDashboardResult.Payload.Value.ValueKind == JsonValueKind.Object)
        {
            var benchmark = benchmarkDashboardResult.Payload.Value;
            if (TryGetBool(benchmark, "missing", out var benchmarkMissing) && benchmarkMissing)
            {
                lines.Add("Benchmark dashboard:");
                lines.Add("- No benchmark history yet.");
                lines.Add("- Run benchmark history to capture the first model dashboard snapshot.");
            }
            else
            {
                benchmark.TryGetProperty("dashboard", out var dashboard);
                benchmark.TryGetProperty("gate", out var gate);
                benchmark.TryGetProperty("alert_routes", out var alertRoutes);
                dashboard.TryGetProperty("latest_run", out var latestRun);
                lines.Add("Benchmark dashboard:");
                lines.Add($"- History count: {ReadNumber(benchmark, "history_count")}");
                lines.Add($"- Latest run: {ReadString(benchmark, "latest_run_label")}");
                lines.Add($"- Gate: {ReadString(gate, "status")}");
                lines.Add($"- Primary perplexity: {ReadString(latestRun, "primary_perplexity")}");
                lines.Add($"- Highest alert severity: {ReadString(alertRoutes, "highest_severity")}");
                lines.Add($"- Alert routes: {ReadNumber(alertRoutes, "route_count")}");
                lines.Add($"- Route counts: {ReadObjectPairs(alertRoutes, "route_counts")}");
                lines.Add($"- Top families: {ReadArrayFieldPreview(dashboard, "family_slices", "family", 3)}");
            }
        }
        else
        {
            lines.Add("Benchmark dashboard:");
            lines.Add(benchmarkDashboardResult.DisplayText());
        }

        lines.Add("");
        if (benchmarkAlertsResult.Payload.HasValue && benchmarkAlertsResult.Payload.Value.ValueKind == JsonValueKind.Object)
        {
            var routed = benchmarkAlertsResult.Payload.Value;
            if (TryGetBool(routed, "missing", out var alertsMissing) && alertsMissing)
            {
                lines.Add("Benchmark alert routes:");
                lines.Add("- No routed alerts yet.");
            }
            else
            {
                lines.Add("Benchmark alert routes:");
                lines.Add($"- Status: {ReadString(routed, "status")}");
                lines.Add($"- Alert count: {ReadNumber(routed, "alert_count")}");
                lines.Add($"- Highest severity: {ReadString(routed, "highest_severity")}");
                lines.Add($"- Routes: {ReadObjectPairs(routed, "route_counts")}");
            }
        }
        else
        {
            lines.Add("Benchmark alert routes:");
            lines.Add(benchmarkAlertsResult.DisplayText());
        }

        lines.Add("");
        if (benchmarkRemediationResult.Payload.HasValue && benchmarkRemediationResult.Payload.Value.ValueKind == JsonValueKind.Object)
        {
            var remediation = benchmarkRemediationResult.Payload.Value;
            lines.Add("Benchmark remediation:");
            lines.Add($"- Status: {ReadString(remediation, "status")}");
            lines.Add($"- Latest run: {ReadString(remediation, "latest_run_label")}");
            lines.Add($"- Targeted families: {ReadStringArray(remediation, "targeted_families")}");
            if (remediation.TryGetProperty("approval", out var approval) && approval.ValueKind == JsonValueKind.Object)
            {
                var pendingState = "n/a";
                if (approval.TryGetProperty("pending", out var pending) && pending.ValueKind == JsonValueKind.Object)
                {
                    pendingState = ReadString(pending, "state");
                }
                lines.Add($"- Approval pending: {(pendingState == "pending" ? "yes" : "no")}");
                lines.Add($"- Approved ready: {(ReadBool(approval, "approved_ready") ? "yes" : "no")}");
            }
            if (remediation.TryGetProperty("execution", out var execution) && execution.ValueKind == JsonValueKind.Object)
            {
                lines.Add($"- Last execution ok: {(execution.TryGetProperty("latest", out var latestExecution) && latestExecution.ValueKind == JsonValueKind.Object && ReadBool(latestExecution, "ok") ? "yes" : "no")}");
            }
            if (remediation.TryGetProperty("proposal", out var proposal) && proposal.ValueKind == JsonValueKind.Object)
            {
                lines.Add($"- Candidate checkpoint: {ReadString(proposal, "candidate_checkpoint")}");
            }
        }
        else
        {
            lines.Add("Benchmark remediation:");
            lines.Add(benchmarkRemediationResult.DisplayText());
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string BuildLocalModsSummary(NativeCommandResult result)
    {
        if (!result.Payload.HasValue || result.Payload.Value.ValueKind != JsonValueKind.Object)
        {
            return "Private Local Mods" + Environment.NewLine + Environment.NewLine + result.DisplayText();
        }

        var payload = result.Payload.Value;
        var lines = new List<string>
        {
            "Private Local Mods",
            "",
            $"Plugin count: {ReadNumber(payload, "plugin_count")}",
            $"Loadable count: {ReadNumber(payload, "loadable_count")}",
            $"Signed count: {ReadNumber(payload, "signed_count")}",
            $"Invalid count: {ReadNumber(payload, "invalid_count")}",
        };

        if (payload.TryGetProperty("plugins", out var plugins)
            && plugins.ValueKind == JsonValueKind.Array
            && plugins.GetArrayLength() > 0)
        {
            foreach (var plugin in plugins.EnumerateArray().Take(10))
            {
                lines.Add("");
                lines.Add($"- {ReadString(plugin, "name")} [{ReadString(plugin, "kind")}]");
                lines.Add($"  Enabled: {(ReadBool(plugin, "enabled") ? "yes" : "no")}");
                lines.Add($"  Load allowed: {(ReadBool(plugin, "load_allowed") ? "yes" : "no")}");
                lines.Add($"  Trust: {ReadString(plugin, "trust")}");
                lines.Add($"  Signature valid: {ReadString(plugin, "signature_valid")}");
                lines.Add($"  Distribution: {ReadString(plugin, "distribution")}");
                lines.Add($"  Local only: {(ReadBool(plugin, "local_only") ? "yes" : "no")}");
                lines.Add($"  Mutable: {(ReadBool(plugin, "mutable") ? "yes" : "no")}");
                lines.Add($"  Version: {ReadString(plugin, "version")}");
                lines.Add($"  Path: {ReadString(plugin, "path")}");
                lines.Add($"  Issues: {ReadStringArray(plugin, "issues")}");
            }
        }
        else
        {
            lines.Add("");
            lines.Add("No private-local mods are installed yet.");
            lines.Add("Use Browse File or Browse Folder, then Install Local Mod Path.");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private string BuildSystemHealthSummary(NativeCommandResult runtimeResult, NativeCommandResult continuityResult)
    {
        if (!runtimeResult.Payload.HasValue || runtimeResult.Payload.Value.ValueKind != JsonValueKind.Object)
        {
            return "System Health" + Environment.NewLine + Environment.NewLine + runtimeResult.DisplayText();
        }

        var runtimePayload = runtimeResult.Payload.Value;
        runtimePayload.TryGetProperty("runtime_loop", out var runtimeLoop);
        runtimePayload.TryGetProperty("runtime_agent", out var runtimeAgent);
        runtimePayload.TryGetProperty("autonomy", out var autonomy);
        runtimePayload.TryGetProperty("autonomy_background", out var autonomyBackground);

        JsonElement continuityPayload = default;
        var hasContinuityPayload = false;
        if (continuityResult.Payload is JsonElement continuityElement && continuityElement.ValueKind == JsonValueKind.Object)
        {
            continuityPayload = continuityElement;
            hasContinuityPayload = true;
        }

        var runtimeReady = ReadBool(runtimePayload, "runtime_ready");
        var runtimeMissing = ReadBool(runtimePayload, "missing");
        var agentRunning = ReadBool(runtimeAgent, "running");
        var agentInstalled = ReadBool(runtimeAgent, "installed");
        var loopEnabled = ReadBool(runtimeLoop, "enabled");
        var continuityHealthy = hasContinuityPayload
            && ReadNestedBool(continuityPayload, "continuity", "same_system")
            && !ReadNestedBool(continuityPayload, "contradiction_detection", "has_contradiction");
        var continuityScore = hasContinuityPayload ? ReadNestedNumber(continuityPayload, "continuity", "continuity_score") : "n/a";
        var lastFailure = FirstNonEmpty(
            ReadString(runtimeAgent, "last_failure"),
            ReadString(runtimeLoop, "last_failure"),
            runtimeMissing ? "runtime has not been run yet" : ""
        );

        var healthState = "Healthy";
        if (!continuityHealthy)
        {
            healthState = "Needs Attention";
        }
        else if (!agentRunning || !runtimeReady || !loopEnabled)
        {
            healthState = "Setup Needed";
        }

        var recommendedFix = "No immediate action needed.";
        if (!agentInstalled || !agentRunning)
        {
            recommendedFix = "Install and start the background agent.";
        }
        else if (!loopEnabled)
        {
            recommendedFix = "Turn on the runtime loop.";
        }
        else if (!continuityHealthy)
        {
            recommendedFix = "Repair continuity.";
        }
        else if (!runtimeReady || runtimeMissing)
        {
            recommendedFix = "Run the runtime now.";
        }

        var lines = new List<string>
        {
            "System Health",
            "",
            $"Overall: {healthState}",
            $"Recommended fix: {recommendedFix}",
            "",
            $"Zero AI background agent: {(agentRunning ? "running" : "not running")}",
            $"Runtime loop: {(loopEnabled ? "on" : "off")}",
            $"Continuity: {(continuityHealthy ? "healthy" : "needs attention")}",
            $"Continuity score: {continuityScore}",
            $"Runtime ready: {(runtimeReady ? "yes" : "no")}",
            $"Last successful runtime tick: {FirstNonEmpty(ReadString(runtimeLoop, "last_run_utc"), ReadString(runtimeAgent, "last_tick_utc"), "n/a")}",
            $"Last failure: {lastFailure}",
            "",
            $"Agent installed: {(agentInstalled ? "yes" : "no")}",
            $"Agent heartbeat: {ReadString(runtimeAgent, "last_heartbeat_utc")}",
            $"Runtime loop next run: {ReadString(runtimeLoop, "next_run_utc")}",
            $"Auto-enable runtime loop on launch: {(_autoEnableRuntimeLoopOnLaunch ? "yes" : "no")}",
            $"Autonomy current goal: {ReadString(autonomy, "current_goal_title")}",
            $"Autonomy next action: {ReadString(autonomy, "current_goal_next_action")}",
            $"Autonomy loop enabled: {(ReadNestedBool(autonomy, "loop", "enabled") ? "yes" : "no")}",
            $"Autonomy background tick: {(ReadBool(autonomyBackground, "ran") ? "ran" : "idle")}"
        };

        if (hasContinuityPayload)
        {
            lines.Add($"Continuity contradictions: {ReadNestedStringArray(continuityPayload, "contradiction_detection", "issues")}");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private void RunSystemHealthFixNow()
    {
        var runtimeStatus = _backend.RunTask("zero ai runtime status");
        var continuityStatus = _backend.RunTask("zero ai self continuity status");

        JsonElement runtimePayload = default;
        JsonElement runtimeLoop = default;
        JsonElement runtimeAgent = default;
        if (runtimeStatus.Payload.HasValue && runtimeStatus.Payload.Value.ValueKind == JsonValueKind.Object)
        {
            runtimePayload = runtimeStatus.Payload.Value;
            runtimePayload.TryGetProperty("runtime_loop", out runtimeLoop);
            runtimePayload.TryGetProperty("runtime_agent", out runtimeAgent);
        }

        JsonElement continuityPayload = default;
        var hasContinuityPayload = false;
        if (continuityStatus.Payload is JsonElement continuityElement && continuityElement.ValueKind == JsonValueKind.Object)
        {
            continuityPayload = continuityElement;
            hasContinuityPayload = true;
        }

        var commands = new List<(string Command, string Label)>();
        var agentRunning = ReadBool(runtimeAgent, "running");
        var agentInstalled = ReadBool(runtimeAgent, "installed");
        var loopEnabled = ReadBool(runtimeLoop, "enabled");
        var runtimeReady = ReadBool(runtimePayload, "runtime_ready");
        var runtimeMissing = ReadBool(runtimePayload, "missing");
        var continuityHealthy = hasContinuityPayload
            && ReadNestedBool(continuityPayload, "continuity", "same_system")
            && !ReadNestedBool(continuityPayload, "contradiction_detection", "has_contradiction");

        if (!agentInstalled || !agentRunning)
        {
            _autoEnableRuntimeLoopOnLaunch = true;
            SaveRuntimeStartupPreference();
            commands.Add(("zero ai runtime agent install", "Installed and started background agent"));
        }
        else if (!loopEnabled)
        {
            commands.Add(("zero ai runtime loop on interval=180", "Enabled runtime loop"));
        }

        if (!continuityHealthy)
        {
            commands.Add(("zero ai self repair restore continuity", "Repaired continuity"));
        }

        if (!runtimeReady || runtimeMissing || !continuityHealthy)
        {
            commands.Add(("zero ai runtime run", "Ran runtime health pass"));
        }

        if (commands.Count == 0)
        {
            commands.Add(("zero ai runtime run", "Ran runtime health pass"));
        }

        var results = new List<string>
        {
            "System Health Fix Now",
            ""
        };

        foreach (var step in commands)
        {
            SetStatus($"Running health fix: {step.Command}");
            AppendLog($"Running system health fix: {step.Command}");
            var result = _backend.RunTask(step.Command);
            results.Add($"[{step.Label}] {step.Command}");
            results.Add(result.DisplayText());
            results.Add("");
        }

        OutputBox.Text = string.Join(Environment.NewLine, results).TrimEnd();
        SetStatus("System health fix complete.");
        AppendLog("System health fix complete");
        RefreshRuntimeContinuityStatus();
        RefreshSystemHealth();
        RefreshQuickStartStatus();
        RefreshAutonomyStatus();
        RefreshControlMapStatus();
    }

    private void SyncRuntimeLoopTimer(NativeCommandResult result)
    {
        if (!result.Payload.HasValue || result.Payload.Value.ValueKind != JsonValueKind.Object)
        {
            StopRuntimeLoopTimer();
            return;
        }

        var payload = result.Payload.Value;
        payload.TryGetProperty("runtime_agent", out var runtimeAgent);
        if (!payload.TryGetProperty("runtime_loop", out var runtimeLoop) || runtimeLoop.ValueKind != JsonValueKind.Object)
        {
            StopRuntimeLoopTimer();
            return;
        }

        if (ReadBool(runtimeLoop, "enabled") || ReadBool(runtimeAgent, "running"))
        {
            if (!_runtimeLoopTimer.IsEnabled)
            {
                _runtimeLoopTimer.Start();
                AppendLog("Zero AI runtime loop timer started");
            }
        }
        else
        {
            StopRuntimeLoopTimer();
        }
    }

    private void StopRuntimeLoopTimer()
    {
        if (_runtimeLoopTimer.IsEnabled)
        {
            _runtimeLoopTimer.Stop();
            AppendLog("Zero AI runtime loop timer stopped");
        }
    }

    private void RuntimeLoopTimer_Tick(object? sender, EventArgs e)
    {
        if (_runtimeLoopTickInFlight)
        {
            return;
        }

        _runtimeLoopTickInFlight = true;
        try
        {
            var status = _backend.RunTask("zero ai runtime status");
            if (status.Payload.HasValue && status.Payload.Value.ValueKind == JsonValueKind.Object)
            {
                RuntimeContinuityBox.Text = BuildRuntimeContinuitySummary(status)
                    + Environment.NewLine + Environment.NewLine
                    + $"Auto-enable runtime loop on launch: {(_autoEnableRuntimeLoopOnLaunch ? "yes" : "no")}";

                var payload = status.Payload.Value;
                payload.TryGetProperty("runtime_agent", out var runtimeAgent);
                payload.TryGetProperty("runtime_loop", out var runtimeLoop);
                if (ReadBool(runtimeAgent, "running"))
                {
                    return;
                }

                if (ReadBool(runtimeLoop, "enabled") && ReadBool(runtimeLoop, "due_now"))
                {
                    var result = _backend.RunTask("zero ai runtime loop tick");
                    if (result.Payload.HasValue && result.Payload.Value.ValueKind == JsonValueKind.Object)
                    {
                        var tickPayload = result.Payload.Value;
                        if (ReadBool(tickPayload, "ran"))
                        {
                            AppendLog("Zero AI runtime loop tick executed");
                        }
                        else
                        {
                            var reason = ReadString(tickPayload, "reason");
                            if (!string.Equals(reason, "runtime loop not due", StringComparison.OrdinalIgnoreCase)
                                && !string.Equals(reason, "runtime loop is off", StringComparison.OrdinalIgnoreCase))
                            {
                                AppendLog($"Zero AI runtime loop tick skipped: {reason}");
                            }
                        }
                    }
                    RefreshRuntimeContinuityStatus();
                    RefreshSystemHealth();
                    RefreshQuickStartStatus();
                    RefreshAutonomyStatus();
                    RefreshControlMapStatus();
                }
            }
            else if (!status.Ok)
            {
                AppendLog("Zero AI runtime loop timer could not load runtime status");
            }
        }
        finally
        {
            _runtimeLoopTickInFlight = false;
        }
    }

    private static string ReadString(JsonElement element, string propertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(propertyName, out var value))
        {
            return "n/a";
        }

        return value.ValueKind switch
        {
            JsonValueKind.String => value.GetString() ?? "n/a",
            JsonValueKind.Number => value.ToString(),
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            _ => value.ToString()
        };
    }

    private static string ReadNumber(JsonElement element, string propertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(propertyName, out var value))
        {
            return "n/a";
        }

        return value.ValueKind == JsonValueKind.Number ? value.ToString() : "n/a";
    }

    private static string ReadNestedNumber(JsonElement element, string objectPropertyName, string valuePropertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(objectPropertyName, out var nested))
        {
            return "n/a";
        }

        return ReadNumber(nested, valuePropertyName);
    }

    private static string ReadNestedString(JsonElement element, string objectPropertyName, string valuePropertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(objectPropertyName, out var nested))
        {
            return "n/a";
        }

        return ReadString(nested, valuePropertyName);
    }

    private static bool ReadBool(JsonElement element, string propertyName)
    {
        return TryGetBool(element, propertyName, out var value) && value;
    }

    private static bool ReadNestedBool(JsonElement element, string objectPropertyName, string valuePropertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(objectPropertyName, out var nested))
        {
            return false;
        }

        return ReadBool(nested, valuePropertyName);
    }

    private static string ReadNestedStringArray(JsonElement element, string objectPropertyName, string valuePropertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(objectPropertyName, out var nested))
        {
            return "n/a";
        }

        return ReadStringArray(nested, valuePropertyName);
    }

    private static bool TryGetBool(JsonElement element, string propertyName, out bool value)
    {
        value = false;
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(propertyName, out var property))
        {
            return false;
        }

        if (property.ValueKind == JsonValueKind.True)
        {
            value = true;
            return true;
        }

        if (property.ValueKind == JsonValueKind.False)
        {
            value = false;
            return true;
        }

        return false;
    }

    private static string ReadStringArray(JsonElement element, string propertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(propertyName, out var value))
        {
            return "n/a";
        }

        if (value.ValueKind != JsonValueKind.Array)
        {
            return value.ToString();
        }

        var items = value.EnumerateArray()
            .Select(item => item.ValueKind == JsonValueKind.String ? item.GetString() : item.ToString())
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .ToList();

        return items.Count == 0 ? "none" : string.Join(", ", items);
    }

    private static string ReadArrayPreview(JsonElement element, string propertyName, int maxItems = 3)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(propertyName, out var value))
        {
            return "none";
        }

        if (value.ValueKind != JsonValueKind.Array)
        {
            return string.IsNullOrWhiteSpace(value.ToString()) ? "none" : value.ToString();
        }

        var items = value.EnumerateArray()
            .Take(maxItems)
            .Select(item => item.ValueKind == JsonValueKind.String ? item.GetString() : item.ToString())
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .ToList();

        if (items.Count == 0)
        {
            return "none";
        }

        var suffix = value.GetArrayLength() > items.Count ? $" (+{value.GetArrayLength() - items.Count} more)" : string.Empty;
        return string.Join(" | ", items) + suffix;
    }

    private static string ReadObjectPairs(JsonElement element, string propertyName)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(propertyName, out var value))
        {
            return "none";
        }

        if (value.ValueKind != JsonValueKind.Object)
        {
            return string.IsNullOrWhiteSpace(value.ToString()) ? "none" : value.ToString();
        }

        var pairs = value.EnumerateObject()
            .Select(item => $"{item.Name}={item.Value}")
            .Where(item => !string.IsNullOrWhiteSpace(item))
            .ToList();
        return pairs.Count == 0 ? "none" : string.Join(", ", pairs);
    }

    private static string ReadArrayFieldPreview(JsonElement element, string propertyName, string fieldName, int maxItems = 3)
    {
        if (element.ValueKind != JsonValueKind.Object || !element.TryGetProperty(propertyName, out var value))
        {
            return "none";
        }

        if (value.ValueKind != JsonValueKind.Array)
        {
            return string.IsNullOrWhiteSpace(value.ToString()) ? "none" : value.ToString();
        }

        var items = value.EnumerateArray()
            .Take(maxItems)
            .Select(item => ReadString(item, fieldName))
            .Where(item => !string.IsNullOrWhiteSpace(item) && !string.Equals(item, "n/a", StringComparison.OrdinalIgnoreCase))
            .ToList();
        if (items.Count == 0)
        {
            return "none";
        }

        var suffix = value.GetArrayLength() > items.Count ? $" (+{value.GetArrayLength() - items.Count} more)" : string.Empty;
        return string.Join(" | ", items) + suffix;
    }

    private static string FirstNonEmpty(params string[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value) && !string.Equals(value, "n/a", StringComparison.OrdinalIgnoreCase))
            {
                return value;
            }
        }

        return "none";
    }

    private void RefreshCodeIndexStatus()
    {
        var statusResult = _backend.RunTask("zero ai index status");
        var symbolResult = _backend.RunTask("zero ai symbol status");
        var watcherResult = _backend.RunTask("zero ai index watch status");
        CodeIndexBox.Text =
            "Code Index Status" + Environment.NewLine + Environment.NewLine +
            statusResult.DisplayText() + Environment.NewLine + Environment.NewLine +
            "Symbol Index Status" + Environment.NewLine + Environment.NewLine +
            symbolResult.DisplayText() + Environment.NewLine + Environment.NewLine +
            "Watcher Status" + Environment.NewLine + Environment.NewLine +
            watcherResult.DisplayText();
    }

    private void RunCodeIndexTask(string command, string successMessage)
    {
        SetStatus($"Running: {command}");
        AppendLog($"Running code index command: {command}");
        var result = _backend.RunTask(command);
        CodeIndexBox.Text = result.DisplayText();
        if (result.Ok)
        {
            SetStatus(successMessage);
            AppendLog(successMessage);
        }
        else
        {
            SetStatus("Code index command completed. Review output.");
            AppendLog("Code index command completed with review-needed output");
        }
        RefreshCodeIndexStatus();
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
            return;
        }

        StopRuntimeLoopTimer();
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

    private string? SelectedLocalModName()
    {
        var pluginName = string.IsNullOrWhiteSpace(LocalModNameBox.Text) ? null : LocalModNameBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(pluginName))
        {
            SetStatus("Enter a plugin name first.");
            return null;
        }

        return pluginName;
    }

    private static string QuoteCommandArgument(string value)
    {
        return $"\"{value.Replace("\"", "\\\"")}\"";
    }
}
