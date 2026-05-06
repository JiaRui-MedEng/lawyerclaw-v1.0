"""
创建默认管理员账户
用法：python create_admin.py
"""
import sys
from pathlib import Path
import uuid

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from service.models.database import db, User
from werkzeug.security import generate_password_hash
from datetime import datetime

app = create_app()

with app.app_context():
    # 检查是否已有管理员
    admin = User.query.filter_by(username='admin').first()
    
    if admin:
        print('⚠️  管理员账户已存在')
        print(f'   用户名：{admin.username}')
        print(f'   邮箱：{admin.email}')
        print(f'   角色：{admin.role}')
        
        # 询问是否重置密码
        response = input('\n是否重置密码为 admin123？(y/n): ')
        if response.lower() == 'y':
            admin.password_hash = generate_password_hash('admin123', method='pbkdf2:sha256')
            admin.role = 'admin'
            admin.is_superuser = True
            db.session.commit()
            print('✅ 密码已重置为：admin123')
        else:
            print('取消操作')
    else:
        # 创建管理员
        admin = User(
            id='admin-0000-0000-0000-000000000001',
            username='admin',
            email='admin@lawyerclaw.cn',
            password_hash=generate_password_hash('admin123', method='pbkdf2:sha256'),
            role='admin',
            is_superuser=True,
            is_active=True
        )
        
        db.session.add(admin)
        db.session.commit()
        
        print('✅ 管理员账户创建成功！')
        print('\n登录信息:')
        print('   用户名：admin')
        print('   密码：admin123')
        print('   邮箱：admin@lawyerclaw.cn')
        print('\n⚠️  首次登录后请立即修改密码！')
