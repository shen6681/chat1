import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chat_assistant.wechat_reader import ScopedWechatReader


class ReaderTests(unittest.TestCase):
    def test_isolated_context_uses_verified_directory_and_no_login_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);tool=root/'tools'/'WeChatEXP';tool.mkdir(parents=True)
            (tool/'wechat_exp_2.10.20260928.exe').write_bytes(b'synthetic-binary-only')
            old=tool/'.wechat_exp_config.json';old.write_text('{"db_keys":{"private":"synthetic secret"},"last_backup_wxid":"different-account"}')
            backup=root/'user-chosen-backup';backup.mkdir();(backup/'message.db').write_bytes(b'synthetic')
            commands=[]
            class Child:
                stopped=False
                def poll(self):return 0 if self.stopped else None
                def terminate(self):self.stopped=True
                def wait(self,timeout):return 0
            def launch(command,**kw):commands.append((command,kw));return Child()
            with patch('chat_assistant.qq_export.tool_root',return_value=root/'tools'),patch('chat_assistant.wechat_reader.subprocess.Popen',side_effect=launch),patch('chat_assistant.wechat_reader.WechatClient.ready',return_value=True):
                reader=ScopedWechatReader(root/'app',backup,{'wxid':'selected-account','db_path':'C:/synthetic-db'},'a'*32)
                cfg=json.loads(reader.config.read_text(encoding='utf-8'))
                self.assertEqual({'last_backup_data_dir':str(backup),'last_backup_wxid':'selected-account'},cfg)
                command,kw=commands[0]
                self.assertEqual(str(backup),command[command.index('--decrypted-dir')+1])
                self.assertEqual('127.0.0.1',command[command.index('--host')+1])
                self.assertIn('--wechat-no-browser',kw['env']['BROWSER'])
                self.assertIn('synthetic secret',old.read_text())
                reader.verify()
                reader.config.write_text('{"last_backup_wxid":"intruder"}')
                with self.assertRaises(ValueError):reader.verify()
                reader.close()

    def test_changed_database_cannot_mix_in_after_contacts_loaded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);tool=root/'tools'/'WeChatEXP';tool.mkdir(parents=True)
            (tool/'wechat_exp_2.10.20260928.exe').write_bytes(b'synthetic')
            backup=root/'chosen';backup.mkdir();db=backup/'message.db';db.write_bytes(b'before')
            class Child:
                def poll(self):return None
                def terminate(self):pass
                def wait(self,timeout):return 0
            with patch('chat_assistant.qq_export.tool_root',return_value=root/'tools'),patch('chat_assistant.wechat_reader.subprocess.Popen',return_value=Child()),patch('chat_assistant.wechat_reader.WechatClient.ready',return_value=True):
                reader=ScopedWechatReader(root/'app',backup,{'wxid':'selected','db_path':'C:/synthetic'},'b'*32)
                db.write_bytes(b'changed database with more data')
                with self.assertRaises(ValueError):reader.verify()
                reader.close()


if __name__=='__main__':unittest.main()
