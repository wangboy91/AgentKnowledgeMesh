"""Windows 排他同句柄原位写入的隔离小实验（2026-10-12）。

验证：外部已开写句柄 busy、hash 校验后的跨进程写/截断/删/rename/replace
被拒、同 base 至多一次成功、先前外部修改冲突，并演示部分写后退出不原子。
只用 TemporaryDirectory 自建合成文件；不导入产品 app、不访问数据库/凭据。
不实现恢复日志，不改变产品写回开关，不承诺映射 I/O/崩溃恢复/旧缓冲协作。
运行：cd src/server; .venv/Scripts/python.exe scripts/verify_owner_exclusive_write.py
标准输出为 JSON；可保存到仓库忽略的 .workbuddy-ai/verification/。
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from ctypes import wintypes as w

for stream in (sys.stdout,sys.stderr):
    if hasattr(stream,"reconfigure"):
        stream.reconfigure(encoding="utf-8",errors="strict")

READ, WRITE, DELETE = 0x80000000, 0x40000000, 0x10000
OPEN_EXISTING, TRUNCATE_EXISTING = 3, 5
OPEN_REPARSE_POINT = 0x00200000


class FileInfo(ctypes.Structure):
    _fields_ = [('attrs', w.DWORD), ('created', w.FILETIME), ('accessed', w.FILETIME),
                ('written', w.FILETIME), ('volume', w.DWORD), ('size_high', w.DWORD),
                ('size_low', w.DWORD), ('links', w.DWORD), ('index_high', w.DWORD), ('index_low', w.DWORD)]


class Native:
    def __init__(self):
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateFileW': ([w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE],w.HANDLE),
            'CloseHandle': ([w.HANDLE],w.BOOL),
            'GetFileInformationByHandle': ([w.HANDLE,ctypes.POINTER(FileInfo)],w.BOOL),
            'SetFilePointerEx': ([w.HANDLE,ctypes.c_longlong,ctypes.c_void_p,w.DWORD],w.BOOL),
            'ReadFile': ([w.HANDLE,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p],w.BOOL),
            'WriteFile': ([w.HANDLE,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p],w.BOOL),
            'SetEndOfFile': ([w.HANDLE],w.BOOL),
            'FlushFileBuffers': ([w.HANDLE],w.BOOL),
            'DeleteFileW': ([w.LPCWSTR],w.BOOL),
            'MoveFileExW': ([w.LPCWSTR,w.LPCWSTR,w.DWORD],w.BOOL),
        }
        for name,(args,result) in signatures.items():
            function = getattr(self.k,name)
            function.argtypes, function.restype = args,result

    def check(self,success):
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

    def open(self,path,access=READ|WRITE,share=0,creation=OPEN_EXISTING):
        handle = self.k.CreateFileW(str(path),access,share,None,creation,OPEN_REPARSE_POINT,None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def close(self,handle):
        self.check(self.k.CloseHandle(handle))

    def identity(self,handle):
        info = FileInfo()
        self.check(self.k.GetFileInformationByHandle(handle,ctypes.byref(info)))
        if info.attrs & (0x400|0x10):
            raise ValueError('reparse/directory not allowed')
        return (info.volume,info.index_high,info.index_low)

    def read(self,handle):
        self.check(self.k.SetFilePointerEx(handle,0,None,0))
        buffer = ctypes.create_string_buffer(8192)
        count = w.DWORD()
        self.check(self.k.ReadFile(handle,buffer,8192,ctypes.byref(count),None))
        if count.value == 8192:
            raise ValueError('experiment limit exceeded')
        return buffer.raw[:count.value]

    def write(self,handle,data,truncate=True):
        self.check(self.k.SetFilePointerEx(handle,0,None,0))
        count = w.DWORD()
        buffer = ctypes.create_string_buffer(data)
        self.check(self.k.WriteFile(handle,buffer,len(data),ctypes.byref(count),None))
        if count.value != len(data):
            raise OSError('partial WriteFile')
        if truncate:
            self.check(self.k.SetEndOfFile(handle))
        self.check(self.k.FlushFileBuffers(handle))


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def baseline(native,path):
    handle = native.open(path,READ,7)
    try:
        return {'identity':native.identity(handle),'hash':hash_bytes(native.read(handle)),'revision':1}
    finally:
        native.close(handle)


def same_handle_write(native,path,expected,state,data,after_hash=None):
    try:
        handle = native.open(path)
    except OSError as error:
        return {'status':'busy' if error.winerror in (32,33) else 'open_failed','winerror':error.winerror}
    try:
        if native.identity(handle) != tuple(expected['identity']):
            return {'status':'identity_conflict'}
        if state['revision'] != expected['revision'] or hash_bytes(native.read(handle)) != expected['hash']:
            return {'status':'conflict'}
        if after_hash:
            after_hash()
        protected_hash = hash_bytes(native.read(handle))
        if protected_hash != expected["hash"]:
            return {"status":"conflict_after_probe"}
        native.write(handle,data)
        actual = native.read(handle)
        if actual != data:
            return {'status':'unknown'}
        state['revision'] += 1  # 仅实验进程内 revision；没有持久 receipt。
        return {'status':'written','revision':state['revision'],'hash':hash_bytes(actual),'protected_hash_before_write':protected_hash}
    except OSError as error:
        return {'status':'unknown','winerror':error.winerror}
    finally:
        native.close(handle)


def child_probe(path,operation):
    native = Native()
    try:
        if operation == 'write':
            handle = native.open(path,WRITE,7)
            try: native.write(handle,b'external-write')
            finally: native.close(handle)
        elif operation == 'truncate':
            handle = native.open(path,WRITE,7,TRUNCATE_EXISTING)
            native.close(handle)
        elif operation == 'delete':
            native.check(native.k.DeleteFileW(str(path)))
        elif operation == 'rename':
            native.check(native.k.MoveFileExW(str(path),str(path.with_suffix('.renamed')),8))
        elif operation == 'replace':
            candidate = path.with_suffix('.candidate')
            candidate.write_bytes(b'external-replacement')
            native.check(native.k.MoveFileExW(str(candidate),str(path),1|8))
        else:
            raise ValueError('unsupported probe')
        result = {'operation':operation,'allowed':True}
    except OSError as error:
        result = {'operation':operation,'allowed':False,'winerror':error.winerror}
    print(json.dumps(result))


def experiment():
    native = Native()
    rows = []
    with tempfile.TemporaryDirectory(prefix='akm-exclusive-write-experiment-') as directory:
        root = Path(directory)
        (root/'.experiment-owned').write_text('synthetic-files-only',encoding='ascii')
        controls=[]
        for operation in ('write','truncate','delete','rename','replace'):
            control_path=root/('control-'+operation+'.md')
            control_path.write_bytes(b'control-original')
            process=subprocess.run([sys.executable,str(Path(__file__).absolute()),'--probe',str(control_path),'--operation',operation],capture_output=True,text=True,timeout=10,check=True)
            controls.append(json.loads(process.stdout))
        # 1: 外部已开写句柄时，OPEN_EXISTING/share=0 必须 busy，字节不变。
        path = root/'busy.md'; path.write_bytes(b'original-busy')
        expected = baseline(native,path)
        outside = native.open(path,READ|WRITE,7)
        try:
            result = same_handle_write(native,path,expected,{'revision':1},b'new')
            unchanged = path.read_bytes() == b'original-busy'
        finally:
            native.close(outside)
        rows.append({'name':'existing_external_writer_busy','result':result,'bytes_unchanged':unchanged,
                     'passed':result['status']=='busy' and unchanged})
        # 2: 校验 hash 后、写入前暂停，用独立进程确定性尝试普通 I/O。
        path = root/'critical.md'; path.write_bytes(b'critical-original')
        expected = baseline(native,path); probes=[]
        def probe_after_hash():
            for operation in ('write','truncate','delete','rename','replace'):
                command = [sys.executable,str(Path(__file__).absolute()),'--probe',str(path),'--operation',operation]
                process = subprocess.run(command,capture_output=True,text=True,timeout=10,check=True)
                probes.append(json.loads(process.stdout))
        result = same_handle_write(native,path,expected,{'revision':1},b'critical-new',probe_after_hash)
        rows.append({'name':'ordinary_io_blocked_after_hash','result':result,'probes':probes,
                     'unlocked_controls':controls,'final_hash':hash_bytes(path.read_bytes()),'passed':result['status']=='written' and result['protected_hash_before_write']==expected['hash'] and all(p['allowed'] for p in controls) and
                     path.read_bytes()==b'critical-new' and all(not p['allowed'] and p['winerror'] in (5,32,33) for p in probes)})
        # 3: 两个同 base 请求：第一持有句柄，第二 busy，第一完成后同 base 再试 conflict。
        path=root/'two.md'; path.write_bytes(b'two-original'); expected=baseline(native,path)
        state={'revision':1}; held=threading.Event(); release=threading.Event(); result_box=[]
        def wait_after_hash():
            held.set()
            if not release.wait(5): raise RuntimeError('experiment synchronization timeout')
        worker=threading.Thread(target=lambda:result_box.append(same_handle_write(native,path,expected,state,b'first-new',wait_after_hash)))
        worker.start()
        if not held.wait(5): raise RuntimeError('first handle not acquired')
        second=same_handle_write(native,path,expected,state,b'second-new')
        release.set(); worker.join(5)
        if worker.is_alive(): raise RuntimeError('first write did not finish')
        retry=same_handle_write(native,path,expected,state,b'second-new')
        rows.append({'name':'same_base_at_most_one_write','first':result_box[0],'second':second,'retry':retry,
                     'passed':result_box[0]['status']=='written' and second['status']=='busy' and retry['status']=='conflict' and path.read_bytes()==b'first-new' and state['revision']==2})
        # 4: 外部在请求前已修改，必须冲突且保留外部新字节。
        path=root/'prior.md'; path.write_bytes(b'old-base'); expected=baseline(native,path)
        path.write_bytes(b'external-before-request')
        result=same_handle_write(native,path,expected,{'revision':1},b'forbidden-overwrite')
        rows.append({'name':'prior_external_change_conflict','result':result,
                     'passed':result['status']=='conflict' and path.read_bytes()==b'external-before-request'})
        # 5: 同句柄原位写的失败反例：子进程仅写前缀并 flush，然后强制退出。
        path=root/'interrupted.md'; path.write_bytes(b'ORIGINAL-COMPLETE')
        process=subprocess.run([sys.executable,str(Path(__file__).absolute()),'--interrupt',str(path)],capture_output=True,text=True,timeout=10)
        actual=path.read_bytes()
        rows.append({'name':'interruption_exposes_partial_original_path','child_exit':process.returncode,
                     'observed_hex':actual.hex(),'old_hash':hash_bytes(b'ORIGINAL-COMPLETE'),'observed_hash':hash_bytes(actual),
                     'passed':process.returncode==23 and actual==b'NEW!INAL-COMPLETE',
                     'meaning':'反例验证通过：非全有全无；没有恢复日志，不能恢复或给出保存成功'})
    return {'platform':sys.platform,'api':'CreateFileW READ|WRITE share=0 OPEN_EXISTING OPEN_REPARSE_POINT',
            'write_sequence':'same handle read/hash/identity → WriteFile → SetEndOfFile → FlushFileBuffers → reread',
            'cases':rows,'all_observations_matched':all(row['passed'] for row in rows),
            'product_writeback_enabled':False,'safe_atomic_writeback_ready':False,
            'not_verified':['crash recovery/journal','persistent revision/operation receipt','mapped I/O','later stale editor buffer save','malicious ancestor reparse replacement','real multi-device']}


def require_experiment_path(path):
    # 子进程工具模式也拒绝普通路径，避免误将原始用户文件作为实验目标。
    path=path.absolute()
    root=path.parent
    temp_root=Path(tempfile.gettempdir()).resolve()
    if root.parent.resolve()!=temp_root or not root.name.startswith('akm-exclusive-write-experiment-'):
        raise ValueError('only script-owned temporary files allowed')
    if path.suffix!='.md' or root.is_symlink() or path.is_symlink():
        raise ValueError('unexpected experiment path')
    if (root/'.experiment-owned').read_text(encoding='ascii')!='synthetic-files-only':
        raise ValueError('missing synthetic experiment marker')


def main():
    if os.name!='nt': raise SystemExit('Windows only; no product paths accessed')
    parser=argparse.ArgumentParser()
    parser.add_argument('--probe',type=Path)
    parser.add_argument('--operation',choices=['write','truncate','delete','rename','replace'])
    parser.add_argument('--interrupt',type=Path)
    arguments=parser.parse_args()
    if arguments.probe:
        require_experiment_path(arguments.probe)
        child_probe(arguments.probe,arguments.operation); return
    if arguments.interrupt:
        require_experiment_path(arguments.interrupt)
        native=Native(); handle=native.open(arguments.interrupt)
        native.write(handle,b'NEW!',truncate=False)
        os._exit(23)  # 只用于本脚本创建的临时合成文件，演示异常退出后部分原位字节。
    result=experiment()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['all_observations_matched']: raise SystemExit(1)


if __name__=='__main__': main()
