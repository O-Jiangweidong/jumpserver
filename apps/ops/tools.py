import os
import stat
import uuid

import paramiko

from io import StringIO

from django.core.cache import cache

from accounts.const.account import SecretType


TASK_CACHE_PREFIX = 'sftp_download_progress_'
FILE_CACHE_PREFIX = 'sftp_download_file_'


class SFTPTool(object):
    def __init__(self, host, port, username, secret, secret_type):
        self.ssh_client = None
        self.sftp_client = None
        self.connected = False
        self.__auth_info = {
            'hostname': host,
            'port': port,
            'username': username,
            'allow_agent': False,
            'look_for_keys': False
        }
        if secret_type == SecretType.PASSWORD:
            self.__auth_info['password'] = secret
        elif secret_type == SecretType.SSH_KEY:
            private_key = paramiko.RSAKey.from_private_key(StringIO(secret))
            self.__auth_info['pkey'] = private_key

    def connect(self):
        if self.connected:
            return

        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(**self.__auth_info)
            self.sftp_client = self.ssh_client.open_sftp()
            self.connected = True
        except Exception as e:
            self.close()
            raise RuntimeError(f'Failed to retrieve path content: {str(e)}')

    def list_path(self, target_path: str, show_hidden_file=False):
        try:
            file_attrs = self.sftp_client.listdir_attr(target_path)
            result = []
            for attr in file_attrs:
                full_path = os.path.join(target_path, attr.filename)
                if stat.S_ISDIR(attr.st_mode):
                    is_leaf, file_size = False, 0
                else:
                    is_leaf, file_size = True, attr.st_size

                if not show_hidden_file and attr.filename.startswith('.'):
                    continue
                result.append({
                    'name': attr.filename, 'path': full_path, 'is_leaf': is_leaf, 'size': file_size,
                })
                result = sorted(result, key=lambda k: k['name'])
            return result
        except FileNotFoundError:
            raise ValueError(f'Path does not exist: {target_path}')
        except PermissionError:
            raise PermissionError(f'No permission to access the path: {target_path}')
        except Exception as e:
            raise RuntimeError(f'Failed to retrieve path content: {str(e)}')

    def download_files(self, task_id, dest_path, remote_filepaths, chunk_size=1024 * 1024):
        if not self.connected:
            self.connect()

        task_cache_key = f'{TASK_CACHE_PREFIX}{task_id}'
        init_progress = {
            'files': {}, 'task_status': 'running'
        }

        for remote_path in remote_filepaths:
            local_path = os.path.normpath(os.path.join(dest_path, remote_path.lstrip('/')))
            try:
                file_size = self.sftp_client.stat(remote_path).st_size
                init_progress['files'][remote_path] = {
                    'local_path': local_path,
                    'size': file_size,
                    'downloaded': 0,
                    'percent': 0.0,
                    'status': 'pending'
                }
            except Exception as e:
                init_progress['files'][remote_path] = {
                    'local_path': local_path,
                    'size': 0,
                    'downloaded': 0,
                    'percent': 0.0,
                    'status': 'failed',
                    'error': str(e)
                }

        cache.set(task_cache_key, init_progress, timeout=3600)
        for remote_path in remote_filepaths:
            file_progress = init_progress['files'][remote_path]
            if file_progress['status'] == 'failed':
                continue

            file_progress['status'] = 'running'
            cache.set(task_cache_key, init_progress, timeout=3600)
            try:
                local_path = init_progress['files'][remote_path]['local_path']
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with self.sftp_client.open(remote_path, 'rb') as remote_f, open(local_path, 'wb') as local_f:
                    downloaded = 0
                    file_size = file_progress['size']
                    while True:
                        chunk = remote_f.read(chunk_size)
                        if not chunk:
                            break
                        local_f.write(chunk)
                        downloaded += len(chunk)
                        percent = (downloaded / file_size) * 100 if file_size > 0 else 100.0
                        file_progress['downloaded'] = downloaded
                        file_progress['percent'] = round(percent, 2)
                        init_progress['files'][remote_path] = file_progress
                        cache.set(task_cache_key, init_progress, timeout=3600)

                file_info_id = str(uuid.uuid4())
                cache.set(f'{FILE_CACHE_PREFIX}{file_info_id}', {
                    'remote_path': remote_path, 'local_path': local_path,
                }, timeout=3600)
                file_progress['id'] = file_info_id
                file_progress['status'] = 'success'
                init_progress['files'][remote_path] = file_progress
            except Exception as e:
                file_progress['status'] = 'failed'
                file_progress['error'] = str(e)
                init_progress['files'][remote_path] = file_progress
            finally:
                cache.set(task_cache_key, init_progress, timeout=3600)

        init_progress['task_status'] = 'completed'
        cache.set(task_cache_key, init_progress, timeout=3600)

    @classmethod
    def get_download_progress(cls, task_id: str):
        cache_key = f'{TASK_CACHE_PREFIX}{task_id}'
        cache_data = cache.get(cache_key, {})
        file_data = cache_data.get('files', {})
        result = []
        for remote_path, infos in file_data.items():
            infos.pop('local_path', None)
            result.append({'path': remote_path, **infos})
        return {'task_status': cache_data.get('task_status', ''), 'file_info': result}

    @classmethod
    def get_file_info(cls, file_id: str):
        return cache.get(f'{FILE_CACHE_PREFIX}{file_id}', {})

    def close(self):
        if self.sftp_client:
            try:
                self.sftp_client.close()
            except: # noqa
                pass

        if self.ssh_client:
            try:
                self.ssh_client.close()
            except: # noqa
                pass

        self.sftp_client, self.ssh_client, self.connected = None, None, False

    def __del__(self):
        self.close()
