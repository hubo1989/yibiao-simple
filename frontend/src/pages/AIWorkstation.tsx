import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AuditOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileAddOutlined,
  FolderOpenOutlined,
  PaperClipOutlined,
  SearchOutlined,
  SendOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { message } from 'antd';
import { documentApi, projectApi } from '../services/api';
import type { ProjectSummary } from '../types/project';
import './AIWorkstation.css';

const quickCommands = [
  '上传招标文件，生成新项目',
  '打开最近编辑的标书项目',
  '查找已有项目并进入管理',
  '对现有标书执行质量评审',
];

const projectStatusText: Record<string, string> = {
  draft: '草稿',
  in_progress: '编写中',
  reviewing: '审查中',
  completed: '已完成',
};

const AIWorkstation: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [command, setCommand] = useState('');
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      setLoading(true);
      const data = await projectApi.list({ sort_by: 'updated_at', sort_order: 'desc', limit: 12 });
      setProjects(data);
    } catch {
      message.error('项目列表加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const recentProject = projects[0];
  const riskProjects = useMemo(
    () => projects.filter((project) => project.status === 'reviewing' || project.status === 'in_progress').slice(0, 3),
    [projects],
  );

  const openProjectByCommand = () => {
    const keyword = command.trim();
    const matched = keyword
      ? projects.find((project) => project.name.includes(keyword) || keyword.includes(project.name))
      : recentProject;
    if (matched) {
      navigate(`/project/${matched.id}`);
      return;
    }
    navigate('/projects');
  };

  const runCommand = () => {
    const normalized = command.trim();
    if (!normalized) {
      fileInputRef.current?.click();
      return;
    }
    if (normalized.includes('上传') || normalized.includes('新项目')) {
      fileInputRef.current?.click();
      return;
    }
    if (normalized.includes('评审') || normalized.includes('审核')) {
      const target = recentProject;
      if (target) {
        navigate(`/project/${target.id}/review`);
        return;
      }
      message.info('请先上传招标文件创建项目，再上传现有标书进行评审');
      return;
    }
    openProjectByCommand();
  };

  const handleTenderUpload = async (file: File) => {
    const fallbackName = file.name.replace(/\.[^.]+$/, '') || '新标书项目';
    const projectName = command.trim() && !command.includes('上传') ? command.trim() : fallbackName;

    try {
      setCreating(true);
      const project = await projectApi.create({
        name: projectName,
        description: `由招标文件「${file.name}」创建`,
      });
      await documentApi.uploadToProject(project.id, file);
      message.success('项目已创建，招标文件已上传');
      navigate(`/project/${project.id}`);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '创建项目失败');
    } finally {
      setCreating(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <main className="ai-workstation">
      <section className="ai-workstation__hero">
        <p className="ai-workstation__eyebrow">AI Native Bid Platform</p>
        <h1>从一个入口开始处理标书</h1>
        <p>上传招标文件生成项目，查找已有项目继续管理，或对现有标书发起质量评审。</p>

        <div className="ai-workstation__command">
          <ThunderboltOutlined />
          <textarea
            value={command}
            onChange={(event) => setCommand(event.target.value)}
            placeholder="例如：上传招标文件，生成智慧园区投标项目"
            aria-label="AI 工作台指令"
          />
          <button type="button" onClick={() => fileInputRef.current?.click()} aria-label="上传招标文件">
            <PaperClipOutlined />
          </button>
          <button type="button" onClick={runCommand} disabled={creating}>
            <SendOutlined />
            {creating ? '处理中' : '发送'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void handleTenderUpload(file);
            }}
          />
        </div>

        <div className="ai-workstation__commands">
          {quickCommands.map((item) => (
            <button key={item} type="button" onClick={() => setCommand(item)}>
              {item}
            </button>
          ))}
        </div>
      </section>

      <section className="ai-workstation__grid">
        <div className="ai-workstation__panel ai-workstation__panel--wide">
          <div className="ai-workstation__panel-head">
            <div>
              <span>Projects</span>
              <strong>最近项目</strong>
            </div>
            <button type="button" onClick={() => navigate('/projects')}>全部项目</button>
          </div>

          {loading ? (
            <div className="ai-workstation__empty">正在读取项目...</div>
          ) : projects.length === 0 ? (
            <div className="ai-workstation__empty">
              <FileAddOutlined />
              <span>还没有项目，上传招标文件即可开始。</span>
            </div>
          ) : (
            <div className="ai-workstation__project-list">
              {projects.slice(0, 6).map((project) => (
                <button key={project.id} type="button" onClick={() => navigate(`/project/${project.id}`)}>
                  <span>
                    <strong>{project.name}</strong>
                    <small>{project.description || '暂无描述'}</small>
                  </span>
                  <em>{projectStatusText[project.status] || project.status}</em>
                </button>
              ))}
            </div>
          )}
        </div>

        <aside className="ai-workstation__panel">
          <div className="ai-workstation__panel-head">
            <div>
              <span>Next</span>
              <strong>推荐动作</strong>
            </div>
          </div>
          <div className="ai-workstation__actions">
            <button type="button" onClick={() => fileInputRef.current?.click()}>
              <FileAddOutlined />
              <span>
                <strong>上传招标文件</strong>
                <small>创建项目并进入标书处理流程</small>
              </span>
            </button>
            <button type="button" onClick={() => recentProject ? navigate(`/project/${recentProject.id}`) : navigate('/projects')}>
              <FolderOpenOutlined />
              <span>
                <strong>继续最近项目</strong>
                <small>{recentProject?.name || '暂无最近项目'}</small>
              </span>
            </button>
            <button type="button" onClick={() => recentProject ? navigate(`/project/${recentProject.id}/review`) : navigate('/projects')}>
              <AuditOutlined />
              <span>
                <strong>评审现有标书</strong>
                <small>上传投标文件并生成审查报告</small>
              </span>
            </button>
          </div>
        </aside>
      </section>

      <section className="ai-workstation__flow">
        {[
          ['上传招标文件', '解析项目概况、评分项、废标条款和材料需求', <PaperClipOutlined />],
          ['生成标书项目', '目录、响应矩阵、正文、素材引用串行推进', <ThunderboltOutlined />],
          ['质量审查', '响应性、合规性、一致性和 diff 修改可追溯', <CheckCircleOutlined />],
          ['导出交付', '输出 Word、批注版和质量报告', <ClockCircleOutlined />],
        ].map(([title, text, icon]) => (
          <div key={String(title)}>
            <span>{icon}</span>
            <strong>{title}</strong>
            <p>{text}</p>
          </div>
        ))}
      </section>

      {riskProjects.length > 0 && (
        <section className="ai-workstation__panel">
          <div className="ai-workstation__panel-head">
            <div>
              <span>Focus</span>
              <strong>待推进项目</strong>
            </div>
          </div>
          <div className="ai-workstation__risk-list">
            {riskProjects.map((project) => (
              <button key={project.id} type="button" onClick={() => navigate(`/project/${project.id}`)}>
                <SearchOutlined />
                <span>{project.name}</span>
                <em>{projectStatusText[project.status] || project.status}</em>
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  );
};

export default AIWorkstation;
