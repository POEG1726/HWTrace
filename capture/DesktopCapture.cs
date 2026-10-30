using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Diagnostics;
using System.Threading;
using System.Globalization;
using System.Text;
using System.Runtime.InteropServices;

public static class HWTraceDesktopCapture {
    [StructLayout(LayoutKind.Sequential)]
    private struct Rect {
        public int Left, Top, Right, Bottom;
    }
    private delegate bool MonitorCallback(IntPtr monitor, IntPtr dc, ref Rect rect, IntPtr data);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool EnumDisplayMonitors(IntPtr dc, IntPtr clip, MonitorCallback callback,
                                                   IntPtr data);
    [DllImport("user32.dll")]
    public static extern IntPtr GetThreadDpiAwarenessContext();
    [DllImport("user32.dll")]
    public static extern bool AreDpiAwarenessContextsEqual(IntPtr first, IntPtr second);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr GetDC(IntPtr window);
    [DllImport("user32.dll")]
    private static extern int ReleaseDC(IntPtr window, IntPtr dc);
    [DllImport("gdi32.dll", SetLastError = true)]
    private static extern bool BitBlt(IntPtr target, int x, int y, int width, int height,
                                      IntPtr source, int sourceX, int sourceY, uint operation);

    public static void CopyPixels(Graphics target, IntPtr source, Rectangle bounds) {
        IntPtr destination = target.GetHdc();
        try {
            // Graphics.CopyFromScreen rejects combined enum flags; Win32 accepts SRCCOPY |
            // CAPTUREBLT.
            if (!BitBlt(destination, 0, 0, bounds.Width, bounds.Height, source, bounds.Left,
                        bounds.Top, 0x40CC0020))
                throw new InvalidOperationException("Fullscreen pixel copy failed: " +
                                                    Marshal.GetLastWin32Error());
        } finally {
            target.ReleaseHdc(destination);
        }
    }

    private static IntPtr EnterPhysicalPixels() {
        IntPtr old = SetThreadDpiAwarenessContext(new IntPtr(-4)); // Per-monitor aware V2.
        if (old == IntPtr.Zero)
            throw new InvalidOperationException("Cannot enter physical-pixel DPI context: " +
                                                Marshal.GetLastWin32Error());
        return old;
    }

    private static Rectangle EnumerateBounds() {
        bool found = false;
        int left = 0, top = 0, right = 0, bottom = 0;
        MonitorCallback callback = delegate(IntPtr monitor, IntPtr dc, ref Rect rect, IntPtr data) {
            if (rect.Right <= rect.Left || rect.Bottom <= rect.Top)
                return true;
            if (!found) {
                left = rect.Left;
                top = rect.Top;
                right = rect.Right;
                bottom = rect.Bottom;
                found = true;
            } else {
                left = Math.Min(left, rect.Left);
                top = Math.Min(top, rect.Top);
                right = Math.Max(right, rect.Right);
                bottom = Math.Max(bottom, rect.Bottom);
            }
            return true;
        };
        if (!EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, callback, IntPtr.Zero) || !found)
            throw new InvalidOperationException("No active desktop monitors are available.");
        long width = (long)right - left, height = (long)bottom - top;
        if (width <= 0 || height <= 0 || width > 32768 || height > 32768)
            throw new InvalidOperationException("Unsupported physical desktop dimensions.");
        return new Rectangle(left, top, (int)width, (int)height);
    }

    public static Rectangle GetPhysicalBounds() {
        IntPtr old = EnterPhysicalPixels();
        try {
            return EnumerateBounds();
        } finally {
            SetThreadDpiAwarenessContext(old);
        }
    }

    public static HWTraceCapturedFrame CaptureFrame() {
        using (Process self = Process.GetCurrentProcess()) {
            if (!Environment.UserInteractive || self.SessionId == 0)
                throw new InvalidOperationException(
                    "Screenshot requires the logged-in Windows desktop.");
        }
        // All bounds discovery and pixel copying run synchronously on this same thread.
        IntPtr old = EnterPhysicalPixels();
        try {
            Rectangle bounds = EnumerateBounds();
            using (Bitmap image = new Bitmap(
                       bounds.Width, bounds.Height,
                       PixelFormat
                           .Format24bppRgb)) using (Graphics graphics =
                                                        Graphics.FromImage(
                                                            image)) using (MemoryStream stream =
                                                                               new MemoryStream()) {
                DateTime started = DateTime.UtcNow;
                long startedTick = Environment.TickCount64;
                IntPtr screen = GetDC(IntPtr.Zero);
                if (screen == IntPtr.Zero)
                    throw new InvalidOperationException("Desktop DC is unavailable.");
                try {
                    CopyPixels(graphics, screen, bounds);
                } finally {
                    ReleaseDC(IntPtr.Zero, screen);
                }
                long finishedTick = Environment.TickCount64;
                DateTime finished = DateTime.UtcNow;
                image.Save(stream, ImageFormat.Png);
                if (stream.Length > 32L * 1024 * 1024)
                    throw new InvalidOperationException(
                        "Startup screenshot exceeds the 32 MiB upload limit.");
                return new HWTraceCapturedFrame {
                    Png = stream.ToArray(),      Bounds = bounds,
                    StartedAtUtc = started,      FinishedAtUtc = finished,
                    StartedTickMs = startedTick, FinishedTickMs = finishedTick
                };
            }
        } finally {
            SetThreadDpiAwarenessContext(old);
        }
    }
}

public sealed class HWTraceCapturedFrame {
    public byte[] Png;
    public Rectangle Bounds;
    public DateTime StartedAtUtc, FinishedAtUtc;
    public long StartedTickMs, FinishedTickMs;
}

public sealed class HWTraceScreenshotWorker : IDisposable {
    private readonly string command, processName, captureId;
    private Func<HWTraceCapturedFrame> capture;
    private readonly object sync = new object();
    private Thread thread;
    private EventWaitHandle gate;
    private Process upload;
    private volatile bool cancelled, completed;
    public bool IsCompleted {
        get { return completed; }
    }
    public string Error { get; private set; }

    private HWTraceScreenshotWorker(string command, string processName, string captureId,
                                    Func<HWTraceCapturedFrame> capture, bool awaitCollector) {
        this.command = command;
        this.processName = processName;
        this.captureId = captureId;
        this.capture = capture;
        if (awaitCollector)
            gate = new EventWaitHandle(false, EventResetMode.ManualReset,
                                       "Local\\HWTraceCaptureStart-" + captureId);
        thread = new Thread(Run) { IsBackground = true, Name = "HWTrace startup screenshot" };
        try {
            thread.Start();
        } catch {
            if (gate != null)
                gate.Dispose();
            throw;
        }
    }

    public static HWTraceScreenshotWorker Start(string command, string processName,
                                                string captureId) {
        return new HWTraceScreenshotWorker(command, processName, captureId,
                                           HWTraceDesktopCapture.CaptureFrame, true);
    }

    // Also supports uploading an already prepared image without taking another screenshot.
    public static HWTraceScreenshotWorker StartUpload(string command, string processName,
                                                      string captureId, byte[] png,
                                                      DateTime capturedAt) {
        return new HWTraceScreenshotWorker(command, processName, captureId, delegate {
            DateTime now = capturedAt.ToUniversalTime();
            long tick = Environment.TickCount64;
            return new HWTraceCapturedFrame { Png = png,
                                              StartedAtUtc = now,
                                              FinishedAtUtc = now,
                                              StartedTickMs = tick,
                                              FinishedTickMs = tick,
                                              Bounds = new Rectangle(0, 0, 1, 1) };
        }, false);
    }

    private void Run() {
        HWTraceCapturedFrame frame = null;
        try {
            if (gate != null && !gate.WaitOne(10000))
                throw new TimeoutException("Collector startup signal timed out.");
            if (cancelled)
                return;
            frame = capture();
            if (cancelled)
                return;
            Upload(frame);
            Console.Error.WriteLine("HWTrace startup screenshot received: " + captureId + ".png");
        } catch (Exception ex) {
            if (!cancelled) {
                Error = ex.Message;
                Console.Error.WriteLine(
                    "HWTrace startup screenshot failed (collection continues): " + ex.Message);
            }
        } finally {
            if (frame != null)
                frame.Png = null;
            capture = null;
            lock (sync) {
                if (gate != null) {
                    gate.Dispose();
                    gate = null;
                }
            }
            completed = true;
        }
    }

    private void Upload(HWTraceCapturedFrame frame) {
        string text = command.Trim();
        int end;
        string executable, arguments;
        if (text.StartsWith("\"")) {
            end = text.IndexOf('"', 1);
            if (end < 0)
                throw new InvalidOperationException("Invalid quoted SSH executable.");
            executable = text.Substring(1, end - 1);
            arguments = text.Substring(end + 1).TrimStart();
        } else {
            end = text.IndexOf(' ');
            if (end < 0)
                throw new InvalidOperationException("SSH command has no receiver arguments.");
            executable = text.Substring(0, end);
            arguments = text.Substring(end + 1);
        }
        string format = "yyyy-MM-ddTHH:mm:ss.fffZ";
        arguments += " --startup-screenshot " + captureId + " --captured-at " +
                     frame.StartedAtUtc.ToString(format, CultureInfo.InvariantCulture) +
                     " --capture-finished-at " +
                     frame.FinishedAtUtc.ToString(format, CultureInfo.InvariantCulture) +
                     " --capture-tick-ms " +
                     frame.StartedTickMs.ToString(CultureInfo.InvariantCulture) +
                     " --capture-finished-tick-ms " +
                     frame.FinishedTickMs.ToString(CultureInfo.InvariantCulture) +
                     " --source-host " + Environment.MachineName + " --process-name-b64 " +
                     Convert.ToBase64String(Encoding.UTF8.GetBytes(processName));
        using (Process p = new Process()) {
            p.StartInfo.FileName = executable;
            p.StartInfo.Arguments = arguments;
            p.StartInfo.UseShellExecute = false;
            p.StartInfo.CreateNoWindow = true;
            p.StartInfo.RedirectStandardInput = true;
            p.StartInfo.RedirectStandardOutput = true;
            p.StartInfo.RedirectStandardError = true;
            p.Start();
            lock (sync) {
                upload = p;
            }
            try {
                if (cancelled)
                    throw new OperationCanceledException("Screenshot worker cancelled.");
                var stdout = p.StandardOutput.ReadToEndAsync();
                var stderr = p.StandardError.ReadToEndAsync();
                var write = p.StandardInput.BaseStream.WriteAsync(frame.Png, 0, frame.Png.Length);
                if (!write.Wait(20000))
                    throw new TimeoutException("Screenshot transfer timed out.");
                p.StandardInput.Close();
                if (!p.WaitForExit(20000))
                    throw new TimeoutException("Screenshot acknowledgement timed out.");
                if (p.ExitCode != 0 ||
                    stdout.GetAwaiter().GetResult().Trim() != "STORED " + captureId)
                    throw new InvalidOperationException("Screenshot was not acknowledged: " +
                                                        stderr.GetAwaiter().GetResult());
            } finally {
                lock (sync) {
                    upload = null;
                    if (!p.HasExited) {
                        p.Kill(true);
                        p.WaitForExit(2000);
                    }
                }
            }
        }
    }

    public bool Wait(int milliseconds) {
        return thread == null || thread.Join(milliseconds);
    }
    public void Cancel() {
        cancelled = true;
        lock (sync) {
            try {
                if (gate != null)
                    gate.Set();
                if (upload != null && !upload.HasExited)
                    upload.Kill(true);
            } catch (InvalidOperationException) {
            }
        }
    }
    public void Dispose() {
        if (!Wait(2000)) {
            Cancel();
            Wait(2000);
        }
        thread = null;
    }
}
