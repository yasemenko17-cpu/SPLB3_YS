import os
import sys
import errno
import resource
import signal
import re

def parse_limits(text: str) -> dict[str, tuple]:
    """Розбирає вміст /proc/<PID>/limits."""
    lines = text.strip().splitlines()
    result = {}
    if not lines:
        return result
    
    for line in lines[1:]:
        stripped_line = line.strip()
        if not stripped_line:
            continue
        parts = [p.strip() for p in re.split(r'\s{2,}', stripped_line) if p.strip()]
        if len(parts) < 3:
            raise ValueError(f"Некоректний рядок: {stripped_line}")
        
        name = parts[0]
        soft_str = parts[1]
        hard_str = parts[2]
        
        def parse_val(val_str):
            if val_str == 'unlimited':
                return None
            try:
                return int(val_str)
            except ValueError:
                raise ValueError(f"Некоректний рядок: {stripped_line}")
                
        soft = parse_val(soft_str)
        hard = parse_val(hard_str)
        result[name] = (soft, hard)
    return result

def run_limited(job, limits: dict) -> tuple[int | None, int | None]:
    """Виконує функцію job() у дочірньому процесі із застосованими лімітами rlimit."""
    prepared_limits = {}
    for key, val in limits.items():
        rlimit_name = f"RLIMIT_{key}"
        if not hasattr(resource, rlimit_name):
            raise ValueError(f"Невідомий ліміт: {key}")
        rlimit_const = getattr(resource, rlimit_name)
        
        if val is None:
            prepared_limits[rlimit_const] = (resource.RLIM_INFINITY, resource.RLIM_INFINITY)
        elif isinstance(val, int):
            prepared_limits[rlimit_const] = (val, val)
        elif isinstance(val, (tuple, list)) and len(val) == 2:
            s = resource.RLIM_INFINITY if val[0] is None else val[0]
            h = resource.RLIM_INFINITY if val[1] is None else val[1]
            prepared_limits[rlimit_const] = (s, h)
        else:
            raise ValueError(f"Некоректне значення ліміту для {key}")

    pid = os.fork()
    if pid == 0:
        try:
            for rlimit_const, lims in prepared_limits.items():
                resource.setrlimit(rlimit_const, lims)
            
            res = job()
            exit_code = 0 if res is None else res
            os._exit(exit_code)
        except Exception:
            os._exit(3)
    else:
        _, status = os.waitpid(pid, 0)
        if os.WIFEXITED(status):
            return (os.WEXITSTATUS(status), None)
        elif os.WIFSIGNALED(status):
            return (None, os.WTERMSIG(status))
        else:
            return (0, None)

def count_open_until_emfile(limit: int) -> int:
    """Відкриває /dev/null у циклі до досягнення ліміту EMFILE."""
    def job():
        count = 0
        try:
            while True:
                os.open('/dev/null', os.O_RDONLY)
                count += 1
        except OSError as e:
            if e.errno == errno.EMFILE:
                return count
            raise
            
    exit_code, sig = run_limited(job, {'NOFILE': limit})
    if sig is not None or exit_code is None:
        raise RuntimeError("Дитина завершилася аварійно або сигналом")
    return exit_code

def file_size_limit(limit: int, directory: str) -> int:
    """Створює файл та дописує байти до досягнення ліміту EFBIG з ігноруванням SIGXFSZ."""
    def job():
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        filepath = os.path.join(directory, 'data.bin')
        written = 0
        try:
            with open(filepath, 'wb') as f:
                while True:
                    f.write(b'A')
                    f.flush()
                    written += 1
        except OSError as e:
            if e.errno == errno.EFBIG:
                return written
            raise
            
    exit_code, sig = run_limited(job, {'FSIZE': limit})
    if sig is not None or exit_code is None:
        raise RuntimeError("Дитина завершилася аварійно або сигналом")
    return exit_code