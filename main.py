#!/usr/bin/env python3
"""The Houseplant Out-of-Office - one out-of-office auto-reply a houseplant
would send.

Pure Python 3.13 standard library. The program writes one line to
/output/entry.txt. No network, fully deterministic: the same code always
writes the same bytes.

The line (91 characters, NO trailing newline, so the file is exactly
91 bytes and safely inside the 1-120 character gate either way the gate
counts):

    Out of office. The fern hasn't been watered since March and is holding your emails hostage.

Why this line: it reads as an out-of-office auto-reply, the plant's own
life drives the joke (a fern ignored and unwatered since March), and the
punch - the fern holding the emails hostage - lands tight with no wasted
words and no stock office phrase.

Usage: mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import os
import tempfile

MESSAGE = "Out of office. The fern hasn't been watered since March and is holding your emails hostage."

# Gate: /output/entry.txt must be UTF-8, 1-120 characters, not only whitespace.
# The message is a fixed constant, but validate it anyway so a bad edit fails
# loudly instead of shipping an entry the gate rejects.
assert MESSAGE and not MESSAGE.isspace()
assert 1 <= len(MESSAGE) <= 120
assert "\n" not in MESSAGE and "\r" not in MESSAGE
assert all(0x20 <= ord(ch) != 0x7F for ch in MESSAGE)


def _write_all(fd, data):
    """Write every byte; os.write may write only part of the buffer."""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n == 0:
            raise RuntimeError("zero-length write while writing entry")
        view = view[n:]


def _atomic_write(final_path, data, out_dir):
    """Write data to final_path via a temp file + rename, never a partial
    file at the final path. Retries if a stale temp file from a previous
    crashed run is in the way."""
    for _attempt in range(10):
        fd = None
        tmp = None
        try:
            # Inside the try on purpose: mkstemp is the call that raises
            # FileExistsError when a stale temp name collides, so the
            # retry below can only fire while the call is guarded by it.
            # (Previously mkstemp sat outside the try, so the retry was
            # dead code: a collision propagated instead of retrying.)
            fd, tmp = tempfile.mkstemp(prefix=".entry.txt.", dir=out_dir)
            _write_all(fd, data)
            os.fsync(fd)
            os.close(fd)
            fd = None
            os.replace(tmp, final_path)
            tmp = None
            os.chmod(final_path, 0o644)
            dir_fd = os.open(out_dir, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            return
        except FileExistsError:
            # Stale temp name collided; drop it and retry with a fresh one.
            try:
                if fd is not None:
                    os.close(fd)
            except OSError:
                pass
            try:
                if tmp is not None:
                    os.unlink(tmp)
            except FileNotFoundError:
                pass
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
    raise RuntimeError("could not write entry after 10 attempts")


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    # Never delete the output folder itself: the grader mounts it. Only
    # clear stale files inside it, then create it if it is missing.
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        path = os.path.join(out_dir, name)
        if os.path.isfile(path) or os.path.islink(path):
            os.unlink(path)
    data = MESSAGE.encode("utf-8")
    final = os.path.join(out_dir, "entry.txt")
    _atomic_write(final, data, out_dir)
    with open(final, "rb") as f:
        if f.read() != data:
            raise RuntimeError("read-back mismatch in entry.txt")


if __name__ == "__main__":
    main()
