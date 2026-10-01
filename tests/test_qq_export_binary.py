"""Exercise the real unmodified QQNT_Export executable with synthetic SQLite / protobuf."""
import ast
import hashlib
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from chat_assistant.qq_export import export_plain_database, tool_root
from chat_assistant.importers import load_file


class QQExporterBinaryTest(unittest.TestCase):
    def test_real_exporter_produces_importable_private_history_without_login(self):
        tools=tool_root()/"QQNT_Export"
        if not (tools/"QQNT_Export_3.3.0.exe").exists():self.skipTest("Optional bundled QQ exporter absent")
        with zipfile.ZipFile(tools/"QQNT_Export-source-v3.3.0.zip") as z:
            name=next(n for n in z.namelist() if n.endswith('/db/models.py'))
            tree=ast.parse(z.read(name).decode('utf-8'))
        shared={};models={}
        for cls in [n for n in tree.body if isinstance(n,ast.ClassDef)]:
            columns={}
            for n in cls.body:
                if isinstance(n,ast.AnnAssign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='mapped_column':
                    columns[n.target.id]=(ast.literal_eval(n.value.args[0]),'BLOB' if 'bytes' in ast.unparse(n.annotation) else 'INTEGER' if 'int' in ast.unparse(n.annotation) else 'TEXT')
            if cls.name=='Message':shared=columns;continue
            register=next((d for d in cls.decorator_list if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='register_model'),None)
            if not register:continue
            database=ast.literal_eval(register.args[0])
            table=next(ast.literal_eval(n.value) for n in cls.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='__tablename__')
            if any(isinstance(b,ast.Name) and b.id=='Message' for b in cls.bases):columns={**shared,**columns}
            models[cls.name]=(database,table,columns)
        def varint(n):
            result=bytearray()
            while n>127:result.append((n&127)|128);n>>=7
            result.append(n);return bytes(result)
        def text_body(text):
            raw=text.encode('utf-8');element=varint(45002*8)+varint(1)+varint(45101*8+2)+varint(len(raw))+raw
            return varint(40800*8+2)+varint(len(element))+element
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=root/'databases';db.mkdir();connections={}
            for database,table,columns in models.values():
                if database not in connections:connections[database]=sqlite3.connect(db/(database+'.db'))
                connection=connections[database]
                connection.execute('CREATE TABLE "'+table+'" ('+', '.join('"'+column+'" '+kind for column,kind in columns.values())+')')
            def insert(model,values):
                database,table,columns=models[model]
                row={column:values.get(attr) for attr,(column,kind) in columns.items()}
                connections[database].execute('INSERT INTO "'+table+'" ('+', '.join('"'+k+'"' for k in row)+') VALUES ('+','.join('?' for _ in row)+')',list(row.values()))
            insert('UidMapping',{'id':1,'uid':'u_self','qq_num':10001})
            insert('UidMapping',{'id':2,'uid':'u_other','qq_num':10002})
            insert('ProfileInfo',{'uid':'u_self','qq_num':10001,'nickname':'合成账号'})
            insert('ProfileInfo',{'uid':'u_other','qq_num':10002,'nickname':'合成好友'})
            for i,sender,text in [(1,'u_other','今天终于忙完了。'),(2,'u_self','晚上打算怎么放松？'),(3,'u_other','想看个电影。')]:
                insert('C2cMessage',{'id':i,'seq':i,'chat_type':1,'msg_type':2,'sender_uid':sender,'sender_num':10001 if sender=='u_self' else 10002,'time':1790000000+i,'message_body':text_body(text),'interlocutor_uid':'u_other','interlocutor_num':10002})
            for connection in connections.values():connection.commit();connection.close()
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in db.glob('*.db')}
            files=export_plain_database(db,root/'output','10002')
            self.assertEqual(len(files),1)
            c=load_file(files[0]).conversations[0]
            self.assertEqual(c.owner,'u_self');self.assertEqual(len(c.messages),3)
            self.assertEqual([m.speaker for m in c.choose_self(c.owner)],['对方','我','对方'])
            self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in db.glob('*.db')})

if __name__=='__main__':unittest.main()
