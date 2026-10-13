"""严格模式的 owner 只读文件目录；SQLite 状态不保存正文。

只扫描显式配置的根。根不可达或扫描不完整时绝不推导删除。
Windows 持有祖先和目标不共享写入/删除的句柄，读取后释放。
"""
import hashlib
import os
import sqlite3
import stat
import uuid
from pathlib import Path

MAX_CONTENT_BYTES = 1024 * 1024


def content_hash(data):
    return hashlib.sha256(data).hexdigest()


def secure_read(root, relative):
    root = Path(root).absolute()
    parts = relative.split('/')
    if not relative or '\\' in relative or ':' in relative or any(
        p in ('', '.', '..') or p.endswith((' ', '.')) for p in parts
    ):
        raise ValueError('invalid relative path')
    target = root.joinpath(*parts)
    if os.name == 'nt':
        import ctypes
        import msvcrt
        from ctypes import wintypes as w
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
        kernel.CreateFileW.restype = w.HANDLE
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.GetFileInformationByHandleEx.argtypes = [w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD]
        kernel.GetFileInformationByHandleEx.restype = w.BOOL
        handles = []
        try:
            chain = [*reversed(target.parents), target]
            for path in chain:
                handle = kernel.CreateFileW(str(path),0x80000000,1,None,3,0x02200000,None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                handles.append(handle)
                attrs = (w.DWORD * 2)()
                if not kernel.GetFileInformationByHandleEx(handle,9,attrs,ctypes.sizeof(attrs)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if attrs[0] & 0x400:
                    raise ValueError('reparse boundary')
                if path != target and not attrs[0] & 0x10:
                    raise ValueError('not directory')
                if path == target and attrs[0] & 0x10:
                    raise ValueError('not regular file')
            fd = msvcrt.open_osfhandle(handles[-1], os.O_RDONLY | os.O_BINARY)
            handles.pop()
            with os.fdopen(fd, 'rb') as stream:
                data = stream.read(MAX_CONTENT_BYTES + 1)
        finally:
            for handle in reversed(handles):
                kernel.CloseHandle(handle)
    else:
        descriptors = []
        try:
            fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.append(fd)
            for part in (*root.parts[1:], *parts[:-1]):
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                descriptors.append(fd)
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                os.close(fd)
                raise ValueError('not regular file')
            with os.fdopen(fd, 'rb') as stream:
                data = stream.read(MAX_CONTENT_BYTES + 1)
        finally:
            for fd in reversed(descriptors):
                os.close(fd)
    if len(data) > MAX_CONTENT_BYTES:
        raise ValueError('content too large')
    data.decode('utf-8')
    return data


class OwnerReader:
    def __init__(self, roots, state_path):
        self.roots = list(dict.fromkeys(Path(os.path.normcase(os.path.abspath(p))) for p in roots))
        if not self.roots:
            raise ValueError('explicit owner roots required')
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS files(
                file_id TEXT PRIMARY KEY, root TEXT, path TEXT, generation TEXT,
                revision INTEGER, hash TEXT, size INTEGER, deleted INTEGER)''')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS active_owner_path ON files(root,path) WHERE deleted=0')

    def db(self):
        return sqlite3.connect(self.state_path)

    @staticmethod
    def metadata(row, available=True):
        return {'file_id':row[0], 'root_id':str(uuid.uuid5(uuid.NAMESPACE_URL,row[1])),
                'path':row[2], 'generation':row[3], 'revision':row[4], 'hash':row[5],
                'size':row[6], 'deleted':bool(row[7]), 'available':available}

    def scan(self):
        available_roots = set()
        with self.db() as db:
            for root in self.roots:
                paths = []
                errors = []
                try:
                    if not root.is_dir():
                        continue
                    # 空目录同样验证根及祖先，链接/重解析根不得当作删除证据。
                    before = root.stat()
                    for ancestor in [root, *root.parents]:
                        info = ancestor.lstat()
                        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes',0) & 0x400:
                            raise ValueError('reparse root')
                    for directory, folders, files in os.walk(root, onerror=errors.append, followlinks=False):
                        folders[:] = [f for f in folders if not f.startswith('.') and f not in ('node_modules','dist','build')]
                        for folder in folders:
                            info = (Path(directory)/folder).lstat()
                            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & 0x400:
                                errors.append(ValueError('reparse directory'))
                        for name in files:
                            if name.endswith('.md') and not name.startswith('.'):
                                relative = (Path(directory)/name).relative_to(root).as_posix()
                                data = secure_read(root, relative)
                                paths.append((relative,content_hash(data),len(data)))
                    after = root.stat()
                    if errors or (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):
                        continue
                except (OSError, ValueError, UnicodeError):
                    continue
                available_roots.add(str(root))
                found = {p for p,h,s in paths}
                for relative, hash_value, size in paths:
                    row = db.execute('SELECT * FROM files WHERE root=? AND path=? AND deleted=0',(str(root),relative)).fetchone()
                    if row is None:
                        db.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,0)',(str(uuid.uuid4()),str(root),relative,str(uuid.uuid4()),1,hash_value,size))
                    elif row[5] != hash_value:
                        db.execute('UPDATE files SET hash=?,size=?,revision=revision+1 WHERE file_id=?',(hash_value,size,row[0]))
                for row in db.execute('SELECT * FROM files WHERE root=? AND deleted=0',(str(root),)).fetchall():
                    if row[2] not in found:
                        db.execute('UPDATE files SET deleted=1,revision=revision+1 WHERE file_id=?',(row[0],))
            rows = db.execute('SELECT * FROM files').fetchall()
            return [self.metadata(r, r[1] in available_roots) for r in rows]

    def read(self, request):
        if request.get('action') not in ('read', 'search'):
            return {'status':'write_not_supported'}
        # 先扫描修正本地编辑/删除的版本，再验证请求版本；没有隐式路径读入口。
        manifest = self.scan()
        meta = next((m for m in manifest if m['file_id']==request.get('file_id')), None)
        if not meta or meta['deleted'] or meta['generation'] != request.get('generation'):
            return {'status':'deleted'}
        if not meta['available']:
            return {'status':'unavailable'}
        if meta['revision'] != request.get('revision') or meta['hash'] != request.get('hash'):
            return {'status':'conflict'}
        with self.db() as db:
            row = db.execute('SELECT * FROM files WHERE file_id=?',(meta['file_id'],)).fetchone()
        try:
            data = secure_read(row[1],row[2])
            if content_hash(data)!=meta['hash']:
                return {'status':'conflict'}
            text = data.decode('utf-8')
            if request['action']=='search':
                query = request.get('query','')
                position = text.casefold().find(query.casefold()) if query else -1
                return {'status':'ok','file':meta,'snippet':text[max(0,position-60):position+200] if position>=0 else None}
            return {'status':'ok','file':meta,'content':text}
        except (OSError,ValueError,UnicodeError):
            return {'status':'unavailable'}
