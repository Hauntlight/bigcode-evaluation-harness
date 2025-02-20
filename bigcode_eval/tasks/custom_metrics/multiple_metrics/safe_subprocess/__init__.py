import msvcrt
import os
import signal
import subprocess
import time
from typing import List

MAX_BYTES_PER_READ = 1024
SLEEP_BETWEEN_READS = 0.1


class Result:
    timeout: int
    exit_code: int
    stdout: str
    stderr: str

    def __init__(self, timeout, exit_code, stdout, stderr):
        self.timeout = timeout
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


def set_nonblocking(reader):
    """Su Windows, msvcrt.setmode può essere usato per evitare il buffering, ma non esiste un vero O_NONBLOCK."""
    if reader is not None:
        msvcrt.setmode(reader.fileno(), os.O_BINARY)


def run(
    args: List[str],
    timeout_seconds: int = 15,
    max_output_size: int = 2048,
    env=None,
) -> Result:
    """
    Esegue il programma con i dati forniti. Dopo il timeout, termina il processo.
    Cattura fino a max_output_size byte di stdout e stderr.
    """
    p = subprocess.Popen(
        args,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,  # Necessario su Windows
        bufsize=MAX_BYTES_PER_READ,
    )

    set_nonblocking(p.stdout)
    set_nonblocking(p.stderr)

    max_iterations = timeout_seconds * 10
    stdout_saved_bytes = []
    stderr_saved_bytes = []
    stdout_bytes_read = 0
    stderr_bytes_read = 0

    for _ in range(max_iterations):
        if p.stdout:
            this_stdout_read = p.stdout.read(MAX_BYTES_PER_READ)
        else:
            this_stdout_read = None
        
        if p.stderr:
            this_stderr_read = p.stderr.read(MAX_BYTES_PER_READ)
        else:
            this_stderr_read = None

        if this_stdout_read and stdout_bytes_read < max_output_size:
            stdout_saved_bytes.append(this_stdout_read)
            stdout_bytes_read += len(this_stdout_read)
        if this_stderr_read and stderr_bytes_read < max_output_size:
            stderr_saved_bytes.append(this_stderr_read)
            stderr_bytes_read += len(this_stderr_read)

        exit_code = p.poll()
        if exit_code is not None:
            break
        time.sleep(SLEEP_BETWEEN_READS)

    if exit_code is None:
        try:
            p.send_signal(signal.CTRL_BREAK_EVENT)  # Segnale per Windows
            time.sleep(1)  # Attendere la terminazione
            p.terminate()  # Se ancora in esecuzione, termina il processo
        except Exception:
            pass

    timeout = exit_code is None
    exit_code = exit_code if exit_code is not None else -1
    stdout = b"".join(stdout_saved_bytes).decode("utf-8", errors="ignore")
    stderr = b"".join(stderr_saved_bytes).decode("utf-8", errors="ignore")
    
    return Result(timeout=timeout, exit_code=exit_code, stdout=stdout, stderr=stderr)
