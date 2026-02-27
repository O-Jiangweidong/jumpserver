import os
import shutil
import uuid
import json

from django.conf import settings
from django.utils._os import safe_join

from audits.const import OperateChoices
from common.utils import is_macos
from .callback import DefaultCallback
from .exception import CommandInBlackListException
from .interface import interface
from ..utils import get_ansible_log_verbosity, get_logger
from ..tools import SFTPTool


logger = get_logger(__name__)


__all__ = [
    'AdHocRunner', 'PlaybookRunner', 'SuperPlaybookRunner',
    'UploadFileRunner', 'DownloadFileRunner',
]


class AdHocRunner:
    cmd_modules_choices = ('shell', 'raw', 'command', 'script', 'win_shell')
    need_local_connection_modules_choices = ("mysql", "postgresql", "sqlserver", "huawei")

    def __init__(self, inventory, job_module, module, module_args='', pattern='*', project_dir='/tmp/',
                 extra_vars=None,
                 dry_run=False, timeout=-1):
        if extra_vars is None:
            extra_vars = {}
        self.id = uuid.uuid4()
        self.inventory = inventory
        self.pattern = pattern
        self.module = module
        self.job_module = job_module
        self.module_args = module_args
        self.project_dir = project_dir
        self.cb = DefaultCallback()
        self.runner = None
        self.extra_vars = extra_vars
        self.dry_run = dry_run
        self.timeout = timeout
        self.envs = {}

    def check_module(self):
        if self.module not in self.cmd_modules_choices:
            return
        command = self.module_args
        if command and set(command.split()).intersection(set(settings.SECURITY_COMMAND_BLACKLIST)):
            raise CommandInBlackListException(
                "Command is rejected by black list: {}".format(self.module_args))

    def set_local_connection(self):
        if self.job_module in self.need_local_connection_modules_choices:
            self.envs.update({"ANSIBLE_SUPER_MODE": "1"})

    def run(self, verbosity=0, **kwargs):
        self.check_module()
        self.set_local_connection()
        verbosity = get_ansible_log_verbosity(verbosity)

        if not os.path.exists(self.project_dir):
            os.mkdir(self.project_dir, 0o755)
        private_env = safe_join(self.project_dir, 'env')
        if os.path.exists(private_env):
            shutil.rmtree(private_env)

        interface.run(
            timeout=self.timeout if self.timeout > 0 else None,
            extravars=self.extra_vars,
            envvars=self.envs,
            host_pattern=self.pattern,
            private_data_dir=self.project_dir,
            inventory=self.inventory,
            module=self.module,
            module_args=self.module_args,
            verbosity=verbosity,
            event_handler=self.cb.event_handler,
            status_handler=self.cb.status_handler,
            **kwargs
        )
        return self.cb


class PlaybookRunner:
    def __init__(self, inventory, playbook, project_dir='/tmp/', callback=None, extra_vars=None, ):

        self.id = uuid.uuid4()
        self.inventory = inventory
        self.playbook = playbook
        self.project_dir = project_dir
        if not callback:
            callback = DefaultCallback()
        self.cb = callback
        self.isolate = True
        self.envs = {}
        if extra_vars is None:
            extra_vars = {}
        self.extra_vars = extra_vars

    def copy_playbook(self):
        entry = os.path.basename(self.playbook)
        playbook_dir = os.path.dirname(self.playbook)
        project_playbook_dir = os.path.join(self.project_dir, "project")
        shutil.copytree(playbook_dir, project_playbook_dir, dirs_exist_ok=True)
        self.playbook = entry

    def run(self, verbosity=0, **kwargs):
        self.copy_playbook()

        verbosity = get_ansible_log_verbosity(verbosity)
        private_env = safe_join(self.project_dir, 'env')
        if os.path.exists(private_env):
            shutil.rmtree(private_env)

        kwargs = dict(kwargs)
        if self.isolate and not is_macos():
            kwargs['process_isolation'] = True
            kwargs['process_isolation_executable'] = 'bwrap'

        interface.run(
            private_data_dir=self.project_dir,
            inventory=self.inventory,
            playbook=self.playbook,
            verbosity=verbosity,
            event_handler=self.cb.event_handler,
            status_handler=self.cb.status_handler,
            host_cwd=self.project_dir,
            envvars=self.envs,
            extravars=self.extra_vars,
            **kwargs
        )
        return self.cb


class SuperPlaybookRunner(PlaybookRunner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.envs = {"ANSIBLE_SUPER_MODE": "1"}
        self.isolate = False


class FTPLogAuditMixin:
    @staticmethod
    def audit_log(files, operate, job, asset):
        from audits.models import FTPLog

        logs = []
        for file in files:
            data = {
                'user': str(job.creator),
                'remote_addr': '127.0.0.1',
                'asset': asset,
                'account': job.runas,
                'operate': operate,
                'filename': os.path.basename(file['path']),
                'is_success': file['status'],
                'session': '00000000-0000-0000-0000-000000000000',
                'org_id': job.org_id,
            }
            log = FTPLog.objects.create(**data)
            if int(settings.FTP_FILE_MAX_STORE) > 0:
                with open(file['path'], 'rb') as f:
                    __, err = log.save_file_to_storage(f)
                if not err:
                    log.has_file = True
                    logs.append(log)
                else:
                    logger.error(f'Failed to save file to FTP storage: {err}')
        FTPLog.objects.bulk_update(logs, fields=['has_file'])


class UploadFileRunner(FTPLogAuditMixin):
    def __init__(self, inventory, project_dir, job, dest_path, callback=None):
        self.id = uuid.uuid4()
        self.job = job
        self.inventory = inventory
        self.project_dir = project_dir
        self.cb = callback or DefaultCallback()
        upload_file_dir = safe_join(settings.SHARE_DIR, 'job_upload_file')
        self.src_dir = safe_join(upload_file_dir, str(job.id))
        self.dest_dir = safe_join("/", dest_path)

    def _run_ansible_copy(self, src, dest, verbosity, **kwargs):
        interface.run(
            private_data_dir=self.project_dir,
            host_pattern="*",
            inventory=self.inventory,
            module='copy',
            module_args=f"src={src} dest={dest}",
            verbosity=verbosity,
            event_handler=self.cb.event_handler,
            status_handler=self.cb.status_handler,
            **kwargs
        )

    @staticmethod
    def _cleanup_path(path):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
        except OSError as e:
            print(f"del upload tmp dir {path} failed! {e}")

    def get_all_files(self):
        file_paths = []
        if os.path.isfile(self.src_dir):
            file_paths.append({
                'status': True, 'path': os.path.abspath(self.src_dir)
            })
            return file_paths

        if not os.path.isdir(self.src_dir):
            return file_paths

        for root, dirs, files in os.walk(self.src_dir):
            for file in files:
                file_abs_path = os.path.join(root, file)
                file_paths.append({ 'status': True, 'path': file_abs_path})
        return file_paths

    def run(self, verbosity=0, **kwargs):
        __ = kwargs.pop('is_pack_run', True)
        asset = kwargs.pop('asset', '')
        verbosity = get_ansible_log_verbosity(verbosity)
        self._run_ansible_copy(f'{self.src_dir}/', f'{self.dest_dir}/', verbosity, **kwargs)
        self.audit_log(
            files=self.get_all_files(), operate=OperateChoices.upload, job=self.job, asset=asset,
        )
        self._cleanup_path(self.src_dir)
        return self.cb


class DownloadFileRunner:
    def __init__(self, inventory_path, inventory, job, task_id):
        self.id = uuid.uuid4()
        self.job = job
        self.inventory = inventory_path
        self.task_id = task_id
        self.cb = DefaultCallback()
        self._other_info = inventory.get_data()
        args = json.loads(job.args)
        self.src_paths = [p['filename'] for p in args.get('src_path_info', [])]
        file_dir = safe_join(settings.SHARE_DIR, 'job_download_file')
        self.dest_root = safe_join(file_dir, str(job.id))

    def run(self, *args, **kwargs):
        if not self.src_paths:
            raise ValueError("src_paths must be set")

        other_info = self._other_info['all']['hosts']
        if not other_info:
            raise ValueError("asset info must be set")

        base_info = other_info.popitem()[1]
        sftp_port = 0
        for i in base_info['jms_asset'].get('protocols', []):
            if i['name'] == 'sftp':
                sftp_port = i['port']

        asset = base_info['jms_asset']
        account = base_info['jms_account']
        tool = SFTPTool(
            host=asset['address'],  port=sftp_port,
            username=account['username'], secret=account['secret'],
            secret_type=account['secret_type'],
        )
        tool.download_files(str(self.task_id), self.dest_root, self.src_paths)
        self.cb.status = 'successful'
        return self.cb
