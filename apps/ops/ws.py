import asyncio
import os

import aiofiles
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils.translation import gettext_lazy as _
from assets.models import Asset
from common.db.utils import close_old_connections
from common.utils import get_logger, get_object_or_none
from orgs.mixins.ws import OrgMixin
from orgs.utils import tmp_to_org
from perms.utils import PermAssetDetailUtil
from rbac.builtin import BuiltinRole
from .ansible.utils import get_ansible_task_log_path
from .celery.utils import get_celery_task_log_path
from .const import CELERY_LOG_MAGIC_MARK
from .models import CeleryTaskExecution
from .tools import SFTPTool

logger = get_logger(__name__)


class TaskLogWebsocket(AsyncJsonWebsocketConsumer, OrgMixin):
    disconnected = False
    user_tasks = (
        'ops.tasks.run_ops_job',
        'ops.tasks.run_ops_job_execution',
    )

    log_types = {
        'celery': get_celery_task_log_path,
        'ansible': get_ansible_task_log_path
    }

    async def connect(self):
        user = self.scope["user"]
        if user.is_authenticated:
            await self.accept()
            self.cookie = self.get_cookie()
            self.org = self.get_current_org()
        else:
            await self.close()

    def get_log_path(self, task_id, log_type):
        func = self.log_types.get(log_type)
        if func:
            return func(task_id)

    @sync_to_async
    def get_task(self, task_id):
        task = CeleryTaskExecution.objects.filter(id=task_id).first()
        # task.creator 是 foreign key, 会异步去查询的，在下面的 if task.creator 会报错, 所以这里先取出来
        if task and task.creator != ' ':
            return task
        else:
            return None

    @sync_to_async
    def get_current_user_role_ids(self, user):
        with tmp_to_org(self.org):
            org_roles = user.org_roles.all()
        system_roles = user.system_roles.all()
        roles = system_roles | org_roles
        user_role_ids = set(map(str, roles.values_list('id', flat=True)))
        return user_role_ids

    async def receive_json(self, content, **kwargs):
        task_id = content.get('task')
        task = await self.get_task(task_id)
        if not task:
            await self.send_json({'message': 'Task not found', 'task': task_id})
            return

        admin_auditor_role_ids = {
            BuiltinRole.system_admin.id,
            BuiltinRole.system_auditor.id,
            BuiltinRole.org_admin.id,
            BuiltinRole.org_auditor.id
        }
        user = self.scope['user']
        user_role_ids = await self.get_current_user_role_ids(user)
        has_admin_auditor_role = bool(admin_auditor_role_ids & user_role_ids)
        has_perms = await self.has_perms(user, ['audits.view_joblog'])
        user_can_view = task.creator == user or (task.name in self.user_tasks and has_perms)
        # (有管理员或审计员角色) 或者 (任务是用户自己创建的 或者 有查看任务日志权限), 其他情况没有权限
        if not (has_admin_auditor_role or user_can_view):
            await self.send_json({'message': 'No permission', 'task': task_id})
            return

        task_type = content.get('type', 'celery')
        log_path = self.get_log_path(task_id, task_type)
        await self.async_handle_task(task_id, log_path)

    async def async_handle_task(self, task_id, log_path):
        logger.info("Task id: {}".format(task_id))
        timeout = 0
        while not self.disconnected:
            if timeout >= 60:
                await self.send_json({'message': '\r\n', 'task': task_id})
                await self.send_json({'message': 'Task log was not found, the directory may not be shared.',
                                      'task': task_id})
                break
            if not os.path.exists(log_path):
                await self.send_json({'message': '.', 'task': task_id})
                timeout += 0.5
                await asyncio.sleep(0.5)
            else:
                await self.send_task_log(task_id, log_path)
                break

    async def send_task_log(self, task_id, log_path):
        await self.send_json({'message': '\r\n'})
        try:
            logger.debug('Task log path: {}'.format(log_path))
            async with aiofiles.open(log_path, 'rb') as task_log_f:
                while not self.disconnected:
                    data = await task_log_f.read(4096)
                    if data:
                        data = data.replace(b'\n', b'\r\n')
                        await self.send_json(
                            {'message': data.decode(errors='ignore'), 'task': task_id}
                        )
                        if data.find(CELERY_LOG_MAGIC_MARK) != -1:
                            await self.send_json(
                                {'event': 'end', 'task': task_id, 'message': ''}
                            )
                            logger.debug("Task log file magic mark found")
                            break
                    await asyncio.sleep(0.2)
        except OSError as e:
            logger.warning('Task log path open failed: {}'.format(e))

    async def disconnect(self, close_code):
        self.disconnected = True
        close_old_connections()


class TaskFilesWebsocket(AsyncJsonWebsocketConsumer, OrgMixin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sftp_tool = None
        self.current_session = ''

    async def connect(self):
        user = self.scope["user"]
        if user.is_authenticated:
            await self.accept()
            self.cookie = self.get_cookie()
            self.org = self.get_current_org()
        else:
            await self.close()

    @sync_to_async
    def get_asset(self, asset_id):
        with tmp_to_org(self.org):
            return get_object_or_none(Asset, id=asset_id)

    @sync_to_async
    def get_sftp_port(self, asset):
        return asset.get_protocol_port('sftp')

    @sync_to_async
    def get_permed_account(self, asset, run_as):
        tool = PermAssetDetailUtil(self.scope["user"], asset)
        with tmp_to_org(asset.org):
            protocols = tool.get_permed_protocols_for_user(only_name=True)
            if 'all' not in protocols and 'sftp' not in protocols:
                return None
            permed_accounts = tool.get_permed_accounts_for_user()
            accounts_mapper = {account.username: account for account in permed_accounts}
            account = accounts_mapper.get(run_as)
            return account

    @sync_to_async(thread_sensitive=False)
    def get_sftp_tool(self, asset, account, sftp_port):
        if self.sftp_tool:
            self.sftp_tool.close()

        self.sftp_tool = SFTPTool(
            host=asset.address,
            port=sftp_port,
            username=account.username,
            secret=account.secret,
            secret_type=account.secret_type,
        )
        self.sftp_tool.connect()
        self.current_session = ''

    @sync_to_async(thread_sensitive=False)
    def sftp_list_path(self, target_path, show_hidden_file):
        return self.sftp_tool.list_path(target_path, show_hidden_file)

    @sync_to_async
    def close_sftp_tool(self):
        if self.sftp_tool:
            self.sftp_tool.close()
            self.sftp_tool = None
        self.current_session = ''

    async def handle_list_path(self, content):
        asset_id = content.get('asset_id')
        run_as = content.get('run_as')
        target = content.get('target')
        if not all([asset_id, run_as, target]):
            params = 'asset_id, run_as, target'
            await self.send_json({'error': _('The value in the parameter must contain %s') % params})
            return

        if not target.startswith('/'):
            await self.send_json({'error': f"{_('Invalid file path')}: {target}"})
            return

        session = f'{asset_id}_{run_as}'
        if not (self.sftp_tool and self.current_session == session):
            asset = await self.get_asset(asset_id)
            if not asset:
                err_msg = _('Invalid pk \"{pk_value}\" - object does not exist.')
                await self.send_json({'error': err_msg.format(pk_value=asset_id)})
                return

            sftp_port = await self.get_sftp_port(asset)
            if not sftp_port:
                await self.send_json({'error': _('Protocol not found or port incorrect: %s') % sftp_port})
                return

            account = await self.get_permed_account(asset, run_as)
            if not account:
                await self.send_json({'error': _('%s object does not exist.') % run_as})
                return

            await self.get_sftp_tool(asset, account, sftp_port)
            self.current_session = session
        try:
            show_hidden_file = content.get('show_hidden_file', False)
            paths = await self.sftp_list_path(target, show_hidden_file)
            await self.send_json({'action': 'list_path', 'items': paths})
        except Exception as e:
            await self.close_sftp_tool()
            await self.send_json({'error': str(e)})

    @sync_to_async
    def get_info_from_cache(self, task_id):
        return SFTPTool.get_download_progress(task_id)

    async def handle_download_info(self, content):
        task_id = content.get('task_id')
        if not task_id:
            await self.send_json({'error': _('%s object does not exist.') % task_id})
            return

        info = await self.get_info_from_cache(task_id)
        await self.send_json({'action': 'download_info', 'items': info})

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        if action == 'list_path':
            await self.handle_list_path(content)
        elif action == 'download_info':
            await self.handle_download_info(content)
        else:
            await self.send_json({'error': _('Invalid choice: {}').format(action)})

    async def disconnect(self, close_code):
        self.current_session = ''
        close_old_connections()
