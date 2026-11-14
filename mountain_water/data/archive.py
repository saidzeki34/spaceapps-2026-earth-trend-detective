"""Bounded read-only access to members of the pinned CAMELS-CH ZIP archive."""
import io
import re
import zipfile

import httpx

ARCHIVE_URL = "https://zenodo.org/records/15025258/files/camels_ch.zip?download=1"


class RangeReader(io.RawIOBase):
    def __init__(self, client):
        self.client, self.position = client, 0
        data, total = self._range(0, 0)
        if len(data) != 1:
            raise ValueError("Invalid ZIP range response.")
        self.size = total

    def _range(self, start, end):
        with self.client.stream("GET", ARCHIVE_URL, headers={"Range": f"bytes={start}-{end}"}) as r:
            r.raise_for_status()
            expected = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", r.headers.get("Content-Range", ""))
            if r.status_code != 206 or not expected or tuple(map(int, expected.groups()[:2])) != (start, end):
                raise ValueError("Archive server did not honor the bounded range request.")
            data = bytearray()
            for chunk in r.iter_bytes():
                data.extend(chunk)
                if len(data) > end - start + 1:
                    raise ValueError("Archive range exceeded its declared size.")
            if len(data) != end - start + 1:
                raise ValueError("Truncated archive response.")
            return bytes(data), int(expected.group(3))

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        return self.position

    def read(self, size=-1):
        size = self.size - self.position if size < 0 else min(size, self.size - self.position)
        if size <= 0:
            return b""
        if size > 40_000_000:
            raise ValueError("Archive request is too large.")
        content, total = self._range(self.position, self.position + size - 1)
        if total != self.size:
            raise ValueError("Archive changed during retrieval.")
        self.position += len(content)
        return content


def fetch_member(member: str, *, max_bytes=2_000_000, timeout=30, client=None):
    """ZIP CRC is verified by zipfile; whole-archive MD5 is not claimed."""
    owned = client is None
    client = client or httpx.Client(timeout=timeout, follow_redirects=True)
    try:
        with zipfile.ZipFile(RangeReader(client)) as archive:
            info = archive.getinfo(member)
            if info.file_size > max_bytes or info.compress_size > 40_000_000:
                raise ValueError("Requested archive member exceeds the bounded download size.")
            return archive.read(member)
    finally:
        if owned:
            client.close()
