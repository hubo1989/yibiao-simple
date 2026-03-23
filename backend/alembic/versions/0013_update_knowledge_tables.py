"""update knowledge tables for PageIndex

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '0013_update_knowledge_tables'
down_revision = '0011_create_global_prompts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 检查 knowledge_docs 表是否存在
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'knowledge_docs' not in tables:
        # 如果表不存在，创建新表
        op.create_table(
            'knowledge_docs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.String(500), nullable=False),
            sa.Column('title', sa.String(500), nullable=False),
            sa.Column('doc_type', sa.String(50), nullable=False),
            sa.Column('scope', sa.String(50), nullable=False),
            sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('content_source', sa.String(20), nullable=False),
            sa.Column('content', sa.Text, nullable=True),
            sa.Column('file_path', sa.String(500), nullable=True),
            sa.Column('file_type', sa.String(20), nullable=True),
            sa.Column('pageindex_tree', postgresql.JSONB, nullable=True),
            sa.Column('pageindex_status', sa.String(20), nullable=False),
            sa.Column('pageindex_error', sa.Text, nullable=True),
            sa.Column('tags', postgresql.JSONB, nullable=True),
            sa.Column('keywords', postgresql.JSONB, nullable=True),
            sa.Column('category', sa.String(100), nullable=True),
            sa.Column('usage_count', sa.Integer, nullable=False, server_default='0'),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('original_file_name', sa.String(255), nullable=True),
            sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL')
        )
        
        # 创建索引
        op.create_index('ix_knowledge_docs_title', 'knowledge_docs', ['title'])
        op.create_index('ix_knowledge_docs_doc_type', 'knowledge_docs', ['doc_type'])
        op.create_index('ix_knowledge_docs_scope', 'knowledge_docs', ['scope'])
        op.create_index('ix_knowledge_docs_owner_id', 'knowledge_docs', ['owner_id'])
        op.create_index('ix_knowledge_docs_pageindex_status', 'knowledge_docs', ['pageindex_status'])
        op.create_index('ix_knowledge_docs_uploaded_by', 'knowledge_docs', ['uploaded_by'])
        
    else:
        # 如果表已存在，更新表结构
        # 1. 添加新列
        columns = [col['name'] for col in inspector.get_columns('knowledge_docs')]

        if 'name' not in columns:
            op.add_column('knowledge_docs', sa.Column('name', sa.String(500), nullable=True))
            op.execute("UPDATE knowledge_docs SET name = title WHERE name IS NULL")
            op.alter_column('knowledge_docs', 'name', nullable=False)

        if 'title' not in columns:
            op.add_column('knowledge_docs', sa.Column('title', sa.String(500), nullable=True))
            # 将 name 列的数据复制到 title
            op.execute("UPDATE knowledge_docs SET title = name WHERE title IS NULL")
            op.alter_column('knowledge_docs', 'title', nullable=False)
        
        if 'scope' not in columns:
            op.add_column('knowledge_docs', sa.Column('scope', sa.String(50), nullable=True))
            op.execute("UPDATE knowledge_docs SET scope = 'user' WHERE scope IS NULL")
            op.alter_column('knowledge_docs', 'scope', nullable=False)
        
        if 'owner_id' not in columns:
            op.add_column('knowledge_docs', sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True))
        
        if 'content_source' not in columns:
            op.add_column('knowledge_docs', sa.Column('content_source', sa.String(20), nullable=True))
            op.execute("UPDATE knowledge_docs SET content_source = 'file' WHERE content_source IS NULL")
            op.alter_column('knowledge_docs', 'content_source', nullable=False)
        
        if 'content' not in columns:
            op.add_column('knowledge_docs', sa.Column('content', sa.Text, nullable=True))
        
        if 'file_path' not in columns:
            op.add_column('knowledge_docs', sa.Column('file_path', sa.String(500), nullable=True))
        
        if 'file_type' not in columns:
            op.add_column('knowledge_docs', sa.Column('file_type', sa.String(20), nullable=True))
        
        if 'pageindex_tree' not in columns:
            op.add_column('knowledge_docs', sa.Column('pageindex_tree', postgresql.JSONB, nullable=True))
        
        if 'pageindex_status' not in columns:
            op.add_column('knowledge_docs', sa.Column('pageindex_status', sa.String(20), nullable=True))
            op.execute("UPDATE knowledge_docs SET pageindex_status = 'pending' WHERE pageindex_status IS NULL")
            op.alter_column('knowledge_docs', 'pageindex_status', nullable=False)
        
        if 'pageindex_error' not in columns:
            op.add_column('knowledge_docs', sa.Column('pageindex_error', sa.Text, nullable=True))
        
        if 'tags' not in columns:
            op.add_column('knowledge_docs', sa.Column('tags', postgresql.JSONB, nullable=True))
        
        if 'keywords' not in columns:
            op.add_column('knowledge_docs', sa.Column('keywords', postgresql.JSONB, nullable=True))
        
        if 'category' not in columns:
            op.add_column('knowledge_docs', sa.Column('category', sa.String(100), nullable=True))
        
        if 'usage_count' not in columns:
            op.add_column('knowledge_docs', sa.Column('usage_count', sa.Integer, nullable=False, server_default='0'))
        
        if 'last_used_at' not in columns:
            op.add_column('knowledge_docs', sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True))
        
        # 2. 跳过 doc_type 枚举值更新（旧数据可能不存在）
        # op.execute("""
        #     UPDATE knowledge_docs
        #     SET doc_type = 'history_bid'
        #     WHERE doc_type = 'qualification'
        # """)
        # op.execute("""
        #     UPDATE knowledge_docs
        #     SET doc_type = 'company_info'
        #     WHERE doc_type IN ('technical', 'other')
        # """)
        
        # 3. 创建索引
        try:
            op.create_index('ix_knowledge_docs_title', 'knowledge_docs', ['title'])
        except:
            pass
        try:
            op.create_index('ix_knowledge_docs_scope', 'knowledge_docs', ['scope'])
        except:
            pass
        try:
            op.create_index('ix_knowledge_docs_owner_id', 'knowledge_docs', ['owner_id'])
        except:
            pass
        try:
            op.create_index('ix_knowledge_docs_pageindex_status', 'knowledge_docs', ['pageindex_status'])
        except:
            pass
    
    # 创建使用记录表
    if 'project_knowledge_usage' not in tables:
        op.create_table(
            'project_knowledge_usage',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('knowledge_doc_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('chapter_id', sa.String(100), nullable=False),
            sa.Column('used_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['knowledge_doc_id'], ['knowledge_docs.id'], ondelete='CASCADE')
        )
        
        op.create_index('ix_project_knowledge_usage_project_id', 'project_knowledge_usage', ['project_id'])
        op.create_index('ix_project_knowledge_usage_knowledge_doc_id', 'project_knowledge_usage', ['knowledge_doc_id'])


def downgrade() -> None:
    # 删除使用记录表
    op.drop_index('ix_project_knowledge_usage_knowledge_doc_id', table_name='project_knowledge_usage')
    op.drop_index('ix_project_knowledge_usage_project_id', table_name='project_knowledge_usage')
    op.drop_table('project_knowledge_usage')
    
    # 删除 knowledge_docs 表的索引
    try:
        op.drop_index('ix_knowledge_docs_pageindex_status', table_name='knowledge_docs')
    except:
        pass
    try:
        op.drop_index('ix_knowledge_docs_owner_id', table_name='knowledge_docs')
    except:
        pass
    try:
        op.drop_index('ix_knowledge_docs_scope', table_name='knowledge_docs')
    except:
        pass
    try:
        op.drop_index('ix_knowledge_docs_title', table_name='knowledge_docs')
    except:
        pass
    
    # 删除新增的列
    op.drop_column('knowledge_docs', 'last_used_at')
    op.drop_column('knowledge_docs', 'usage_count')
    op.drop_column('knowledge_docs', 'category')
    op.drop_column('knowledge_docs', 'keywords')
    op.drop_column('knowledge_docs', 'tags')
    op.drop_column('knowledge_docs', 'pageindex_error')
    op.drop_column('knowledge_docs', 'pageindex_status')
    op.drop_column('knowledge_docs', 'pageindex_tree')
    op.drop_column('knowledge_docs', 'file_type')
    op.drop_column('knowledge_docs', 'file_path')
    op.drop_column('knowledge_docs', 'content')
    op.drop_column('knowledge_docs', 'content_source')
    op.drop_column('knowledge_docs', 'owner_id')
    op.drop_column('knowledge_docs', 'scope')
    op.drop_column('knowledge_docs', 'title')
    op.drop_column('knowledge_docs', 'name')
