"""Single place where the app runs external commands."""
import subprocess


def run(cmd, timeout=10):
    """Run cmd and return (stdout, error); exactly one of them is None."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    if proc.returncode != 0:
        return None, proc.stderr.strip() or proc.stdout.strip() or f"{cmd[0]} exited with {proc.returncode}"
    return proc.stdout, None
