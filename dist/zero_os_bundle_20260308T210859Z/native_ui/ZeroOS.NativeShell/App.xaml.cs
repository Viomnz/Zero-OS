using System.Windows;
using System.Windows.Threading;
using System.IO;

namespace ZeroOS.NativeShell;

public partial class App : Application
{
    private NativeDiagnostics? _diagnostics;

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        var repoRoot = ResolveRepoRoot();
        _diagnostics = new NativeDiagnostics(repoRoot);

        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnUnhandledException;
    }

    private static string ResolveRepoRoot()
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

    private void OnDispatcherUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
    {
        _diagnostics?.RecordCrash(e.Exception);
        MessageBox.Show(
            "Zero OS Native Shell hit an unexpected error. A crash log was saved under .zero_os/native_shell.",
            "Application Error",
            MessageBoxButton.OK,
            MessageBoxImage.Error
        );
    }

    private void OnUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        if (e.ExceptionObject is Exception ex)
        {
            _diagnostics?.RecordCrash(ex);
        }
    }
}
