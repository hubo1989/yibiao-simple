import React, { useMemo, useState } from 'react';
import {
  ArrowRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloudUploadOutlined,
  ExclamationCircleOutlined,
  ExportOutlined,
  FileDoneOutlined,
  FileSearchOutlined,
  FolderOpenOutlined,
  PaperClipOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RightOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SendOutlined,
  SettingOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UploadOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import './AINativePrototype.css';

type PrototypeView = 'home' | 'projects' | 'materials' | 'templates' | 'settings' | 'project';
type StepKey = 'upload' | 'analysis' | 'matrix' | 'outline' | 'draft' | 'review' | 'export';
type StepStatus = 'done' | 'active' | 'ready' | 'locked' | 'risk';

interface ProjectStep {
  key: StepKey;
  title: string;
  status: StepStatus;
  summary: string;
  dataState: string;
  action: string;
}

interface RecentProject {
  name: string;
  stage: string;
  risk: string;
  updated: string;
  status: StepStatus;
}

const commonCommands = [
  '上传招标文件，生成新项目',
  '打开最近编辑的标书项目',
  '查找待处理风险并给出修复建议',
  '继续生成当前章节内容',
];

const promptChips = ['新建标书项目', '继续最近项目', '查看待处理风险'];

const recentProjects: RecentProject[] = [
  {
    name: '智慧园区综合治理平台投标',
    stage: '质量审查',
    risk: '2 个评分项缺证据',
    updated: '12 分钟前',
    status: 'risk',
  },
  {
    name: '城市数据中台升级项目',
    stage: '章节生成',
    risk: '素材已匹配 18/21',
    updated: '昨天 18:42',
    status: 'done',
  },
  {
    name: '政务云安全服务采购',
    stage: '响应矩阵',
    risk: '1 个废标条款待确认',
    updated: '周一 09:15',
    status: 'risk',
  },
];

const projectSteps: ProjectStep[] = [
  {
    key: 'upload',
    title: '上传招标文件',
    status: 'done',
    summary: '招标文件、评分办法和附件清单已归档，原文可随时回看。',
    dataState: '已有数据，可跳转',
    action: '查看文件',
  },
  {
    key: 'analysis',
    title: '解析确认',
    status: 'done',
    summary: '项目概况、技术要求、资格条件、评分项和废标条款已确认。',
    dataState: '已确认',
    action: '复核解析',
  },
  {
    key: 'matrix',
    title: '响应矩阵',
    status: 'risk',
    summary: '47 条条款已建矩阵，服务方案和团队配置仍缺少可引用证据。',
    dataState: '有风险',
    action: '补齐证据',
  },
  {
    key: 'outline',
    title: '目录章节',
    status: 'done',
    summary: '三级目录已绑定评分项，25 个章节中 18 个已有正文。',
    dataState: '已有数据，可跳转',
    action: '编辑目录',
  },
  {
    key: 'draft',
    title: '内容生成',
    status: 'active',
    summary: '当前正在补写 4.3 售后服务保障，需确认 2 小时响应承诺。',
    dataState: '进行中',
    action: '继续生成',
  },
  {
    key: 'review',
    title: '质量审查',
    status: 'ready',
    summary: '响应性、合规性、一致性审查已可执行，建议先处理矩阵风险。',
    dataState: '可执行',
    action: '开始审查',
  },
  {
    key: 'export',
    title: '导出交付',
    status: 'locked',
    summary: '正式 Word、批注版和质量报告将在风险清零后开放导出。',
    dataState: '等待前置完成',
    action: '查看门禁',
  },
];

const statusConfig: Record<StepStatus, { label: string; icon: React.ReactNode; className: string }> = {
  done: { label: '已完成', icon: <CheckCircleOutlined />, className: 'done' },
  active: { label: '当前步骤', icon: <PlayCircleOutlined />, className: 'active' },
  ready: { label: '可执行', icon: <ClockCircleOutlined />, className: 'ready' },
  locked: { label: '门禁未开放', icon: <SafetyCertificateOutlined />, className: 'locked' },
  risk: { label: '需处理', icon: <WarningOutlined />, className: 'risk' },
};

const matrixRows = [
  ['售后服务响应', '评分项 3.2', '4.3 售后服务保障', '缺 SLA 证据', 'risk'],
  ['项目团队配置', '资格条件 2.1', '2.2 项目组织', '需补人员证书', 'risk'],
  ['数据安全方案', '技术要求 5.4', '3.1 安全架构', '已覆盖', 'done'],
  ['培训交付计划', '评分项 4.1', '5.2 培训计划', '已覆盖', 'done'],
];

const materialRows = [
  ['营业执照', '证照', '已确认', '2027-08-20'],
  ['ISO27001 证书', '资质', '待复核', '2026-12-31'],
  ['智慧园区案例', '项目案例', '已匹配', '长期有效'],
  ['售后 SLA 案例', '服务承诺', '缺失', '需要上传'],
];

const outlineChapters = [
  { no: '1', title: '项目理解与总体方案', level: 1, status: 'done' as StepStatus, score: '2 项', owner: '已锁定' },
  { no: '1.1', title: '项目背景与建设目标', level: 2, status: 'done' as StepStatus, score: '1 项', owner: '正文完成' },
  { no: '1.2', title: '总体实施思路', level: 2, status: 'done' as StepStatus, score: '1 项', owner: '正文完成' },
  { no: '2', title: '项目组织与团队配置', level: 1, status: 'risk' as StepStatus, score: '3 项', owner: '缺人员证书' },
  { no: '2.1', title: '项目组织架构', level: 2, status: 'done' as StepStatus, score: '1 项', owner: '正文完成' },
  { no: '2.2', title: '核心团队资质', level: 2, status: 'risk' as StepStatus, score: '2 项', owner: '待补证据' },
  { no: '3', title: '技术架构与实施路线', level: 1, status: 'done' as StepStatus, score: '4 项', owner: '正文完成' },
  { no: '4', title: '售后服务保障', level: 1, status: 'active' as StepStatus, score: '3 项', owner: '生成中' },
  { no: '4.1', title: '服务体系与组织保障', level: 2, status: 'done' as StepStatus, score: '1 项', owner: '正文完成' },
  { no: '4.2', title: '服务流程与响应机制', level: 2, status: 'done' as StepStatus, score: '1 项', owner: '正文完成' },
  { no: '4.3', title: 'SLA 承诺与闭环管理', level: 2, status: 'active' as StepStatus, score: '1 项', owner: '当前编辑' },
  { no: '5', title: '培训与交付计划', level: 1, status: 'ready' as StepStatus, score: '2 项', owner: '待生成' },
];

const generatedBlocks = [
  {
    label: '已生成',
    title: '服务响应承诺',
    text: '我方承诺提供 7x24 小时技术支持热线。对于影响核心业务运行的关键故障，2 小时内完成响应并启动远程诊断；对于一般问题，4 小时内给出处理建议。',
    evidence: '引用：历史 SLA 案例 #A12、服务台值班表',
  },
  {
    label: '生成中',
    title: '闭环处理机制',
    text: '所有服务请求将进入统一工单系统，按受理、派单、处理、复核、验收五个节点留痕。项目经理每周输出服务记录，确保问题可追踪、可复盘、可验收。',
    evidence: '引用：运维平台截图、项目周报模板',
  },
  {
    label: '待确认',
    title: '现场支持安排',
    text: '重大活动保障期安排专人驻场，保障范围、响应时段和升级联系人需由投标负责人确认后写入正式版本。',
    evidence: '待确认：驻场人员名单',
  },
];

const diffRows = [
  { type: 'context', text: '4.3 SLA 承诺与闭环管理' },
  { type: 'remove', text: '关键故障将尽快响应，并根据情况安排技术人员处理。' },
  { type: 'add', text: '关键故障 2 小时内响应并启动远程诊断，必要时 4 小时内安排技术人员到场支持。' },
  { type: 'context', text: '所有服务请求进入统一工单系统，形成受理、处理、复核、验收记录。' },
  { type: 'add', text: '补充引用历史 SLA 案例 #A12，用于覆盖评分项 3.2“售后响应能力”。' },
];

const versionRows = [
  ['V3', '已确认版本', 'Hubert · 12:26', '已设为交付候选'],
  ['V2', 'AI 修订建议', 'AI · 12:21', '包含 3 处 diff'],
  ['V1', '章节初稿', '张三 · 11:58', '保留原始生成稿'],
];

function TopNav({
  view,
  onNavigate,
}: {
  view: PrototypeView;
  onNavigate: (view: PrototypeView) => void;
}): React.ReactElement {
  const navItems: Array<{ key: PrototypeView; label: string }> = [
    { key: 'projects', label: '项目' },
    { key: 'materials', label: '素材' },
    { key: 'templates', label: '模板' },
    { key: 'settings', label: '设置' },
  ];

  return (
    <header className="single-ai__topbar">
      <button type="button" className="single-ai__brand" onClick={() => onNavigate('home')}>
        <span><ThunderboltOutlined /></span>
        易标 AI
      </button>
      <nav className="single-ai__nav" aria-label="原型导航">
        {navItems.map((item) => (
          <button
            key={item.key}
            type="button"
            className={view === item.key ? 'single-ai__nav-active' : undefined}
            onClick={() => onNavigate(item.key)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <button type="button" className="single-ai__avatar" aria-label="用户中心">H</button>
    </header>
  );
}

function StatusPill({ status, children }: { status: StepStatus; children?: React.ReactNode }): React.ReactElement {
  const config = statusConfig[status];
  return (
    <em className={`single-ai__mini-state single-ai__mini-state--${config.className}`}>
      {config.icon}
      {children || config.label}
    </em>
  );
}

function GlobalEntry({
  onOpenProject,
  onNavigate,
}: {
  onOpenProject: () => void;
  onNavigate: (view: PrototypeView) => void;
}): React.ReactElement {
  const [command, setCommand] = useState('');
  const [focused, setFocused] = useState(true);

  const runCommand = () => {
    if (command.includes('素材')) {
      onNavigate('materials');
      return;
    }
    if (command.includes('模板') || command.includes('导出')) {
      onNavigate('templates');
      return;
    }
    if (command.includes('设置') || command.includes('成员') || command.includes('日志')) {
      onNavigate('settings');
      return;
    }
    onOpenProject();
  };

  const applyCommand = (value: string) => {
    setCommand(value);
    setFocused(true);
  };

  return (
    <main className="single-ai__home">
      <section className="single-ai__home-main" aria-labelledby="prototype-home-title">
        <p className="single-ai__eyebrow">清澈控制台</p>
        <h1 id="prototype-home-title">今天要推进哪份标书？</h1>
        <p className="single-ai__lead">上传招标文件创建项目，或输入项目名继续处理。</p>

        <div className={`single-ai__command-shell ${focused || command ? 'single-ai__command-shell--open' : ''}`}>
          <label className="single-ai__command-box">
            <span className="single-ai__command-icon"><ThunderboltOutlined /></span>
            <textarea
              aria-label="AI 项目入口"
              value={command}
              onChange={(event) => setCommand(event.target.value)}
              onFocus={() => setFocused(true)}
              placeholder="输入你的任务，例如：打开智慧园区项目，继续处理响应矩阵风险"
            />
          </label>
          <div className="single-ai__command-actions">
            <button type="button" className="single-ai__attach-button" aria-label="上传附件" onClick={() => applyCommand('上传招标文件，生成新项目')}>
              <PaperClipOutlined />
            </button>
            <span>支持 docx / pdf</span>
            <button type="button" className="single-ai__primary-button" onClick={runCommand}>
              <SendOutlined />
              发送
            </button>
          </div>
        </div>

        <div className="single-ai__chips" aria-label="快捷提示">
          {promptChips.map((chip) => (
            <button key={chip} type="button" onClick={() => applyCommand(chip)}>
              {chip}
            </button>
          ))}
        </div>

        {(focused || command) && (
          <section className="single-ai__suggestions" aria-label="常用命令">
            <div className="single-ai__suggestions-title">常用命令</div>
            {commonCommands.map((item, index) => (
              <button
                key={item}
                type="button"
                className="single-ai__suggestion"
                onClick={() => applyCommand(item)}
              >
                <span className="single-ai__suggestion-icon">
                  {index === 0 ? <UploadOutlined /> : index === 1 ? <FolderOpenOutlined /> : index === 2 ? <ExclamationCircleOutlined /> : <FileDoneOutlined />}
                </span>
                <span>{item}</span>
                <kbd>{index === 0 ? 'Enter' : '↵'}</kbd>
              </button>
            ))}
          </section>
        )}
      </section>

      <section className="single-ai__quiet-panels" aria-label="项目概览">
        <div className="single-ai__recent-panel">
          <div className="single-ai__panel-title">
            <span>最近项目</span>
            <button type="button" onClick={() => onNavigate('projects')}>全部</button>
          </div>
          <div className="single-ai__recent-list">
            {recentProjects.slice(0, 2).map((project) => (
              <button key={project.name} type="button" className="single-ai__recent-row" onClick={onOpenProject}>
                <span>
                  <strong>{project.name}</strong>
                  <small>{project.stage} · {project.updated}</small>
                </span>
                <StatusPill status={project.status}>{project.risk}</StatusPill>
                <ArrowRightOutlined />
              </button>
            ))}
          </div>
        </div>

        <aside className="single-ai__next-panel">
          <div className="single-ai__panel-title">
            <span>下一步建议</span>
          </div>
          <p>先补齐 2 个评分项证据</p>
          <button type="button" className="single-ai__ghost-button" onClick={onOpenProject}>
            查看原因
            <ArrowRightOutlined />
          </button>
        </aside>
      </section>
    </main>
  );
}

function ProjectsHub({ onOpenProject }: { onOpenProject: () => void }): React.ReactElement {
  return (
    <main className="single-ai__workspace">
      <PageHeader
        eyebrow="Projects"
        title="项目中心"
        description="演示项目搜索、状态筛选、最近动作和风险入口。"
        action={<button type="button" className="single-ai__primary-button" onClick={onOpenProject}><UploadOutlined />新建项目</button>}
      />
      <div className="single-ai__toolbar">
        <label>
          <SearchOutlined />
          <input placeholder="搜索项目、客户、阶段" />
        </label>
        <button type="button">全部</button>
        <button type="button">有风险</button>
        <button type="button">待导出</button>
      </div>
      <section className="single-ai__object-grid">
        {recentProjects.map((project) => (
          <button key={project.name} type="button" className="single-ai__object-card" onClick={onOpenProject}>
            <span className="single-ai__card-kicker">{project.stage}</span>
            <strong>{project.name}</strong>
            <p>{project.risk}</p>
            <div>
              <small>{project.updated}</small>
              <StatusPill status={project.status} />
            </div>
          </button>
        ))}
      </section>
    </main>
  );
}

function MaterialsHub(): React.ReactElement {
  return (
    <main className="single-ai__workspace">
      <PageHeader
        eyebrow="Materials"
        title="素材库与材料匹配"
        description="演示证照、案例、资质、附件需求识别和人工确认。"
        action={<button type="button" className="single-ai__primary-button"><PaperClipOutlined />上传素材</button>}
      />
      <section className="single-ai__split">
        <div className="single-ai__surface">
          <SectionTitle title="企业素材" meta="12 份素材 · 3 份待复核" />
          <div className="single-ai__table">
            {materialRows.map((row) => (
              <div key={row[0]} className="single-ai__table-row">
                <strong>{row[0]}</strong>
                <span>{row[1]}</span>
                <span>{row[2]}</span>
                <small>{row[3]}</small>
              </div>
            ))}
          </div>
        </div>
        <aside className="single-ai__surface">
          <SectionTitle title="招标文件材料需求" meta="AI 已识别 8 项" />
          <div className="single-ai__task-list">
            <TaskItem status="done" title="营业执照副本" text="已匹配营业执照，需确认是否使用最新版本。" />
            <TaskItem status="risk" title="售后 SLA 案例" text="素材库缺失，建议上传历史服务承诺案例。" />
            <TaskItem status="ready" title="ISO27001 证书" text="存在候选素材，等待人工复核有效期。" />
          </div>
        </aside>
      </section>
    </main>
  );
}

function TemplatesHub({ onOpenProject }: { onOpenProject: () => void }): React.ReactElement {
  return (
    <main className="single-ai__workspace">
      <PageHeader
        eyebrow="Templates"
        title="模板与交付"
        description="演示 Word 模板、导出前门禁、交付包和质量报告。"
        action={<button type="button" className="single-ai__primary-button" onClick={onOpenProject}><ExportOutlined />进入导出检查</button>}
      />
      <section className="single-ai__split">
        <div className="single-ai__surface">
          <SectionTitle title="Word 模板" meta="3 个可用模板" />
          <div className="single-ai__object-list">
            <ObjectLine icon={<FileDoneOutlined />} title="政府采购技术标模板" text="封面、目录、三级标题、页眉页脚已配置" />
            <ObjectLine icon={<FileDoneOutlined />} title="服务类项目模板" text="适合运维、SLA、售后服务章节" />
            <ObjectLine icon={<FileDoneOutlined />} title="批注审查模板" text="输出带问题定位的 Word 批注版" />
          </div>
        </div>
        <aside className="single-ai__surface">
          <SectionTitle title="导出前门禁" meta="5 项检查" />
          <div className="single-ai__task-list">
            <TaskItem status="done" title="目录结构完整" text="25 个章节均已绑定模板层级。" />
            <TaskItem status="risk" title="评分项证据缺失" text="2 个评分项需要补齐引用材料。" />
            <TaskItem status="locked" title="正式交付包" text="风险清零后开放 Word、批注版和质量报告。" />
          </div>
        </aside>
      </section>
    </main>
  );
}

function SettingsHub(): React.ReactElement {
  return (
    <main className="single-ai__workspace">
      <PageHeader
        eyebrow="Governance"
        title="协作与系统治理"
        description="演示成员权限、提示词配置、模型 Key、请求日志和审计入口。"
        action={<button type="button" className="single-ai__primary-button"><SettingOutlined />保存配置</button>}
      />
      <section className="single-ai__split">
        <div className="single-ai__surface">
          <SectionTitle title="项目成员" meta="4 人" />
          <div className="single-ai__object-list">
            <ObjectLine icon={<TeamOutlined />} title="Hubert · Owner" text="可发起审查、导出交付包、管理成员。" />
            <ObjectLine icon={<TeamOutlined />} title="张三 · Editor" text="可编辑章节、确认素材、处理响应矩阵。" />
            <ObjectLine icon={<TeamOutlined />} title="李四 · Reviewer" text="可查看审查报告、下载批注版。" />
          </div>
        </div>
        <aside className="single-ai__surface">
          <SectionTitle title="提示词与模型" meta="演示配置" />
          <div className="single-ai__task-list">
            <TaskItem status="done" title="当前模型" text="DeepSeek Chat · OpenAI compatible endpoint。" />
            <TaskItem status="ready" title="审查提示词" text="响应性、合规性、一致性三组提示词可版本管理。" />
            <TaskItem status="risk" title="请求日志" text="过去 24 小时有 2 次模型超时，已记录重试。" />
          </div>
        </aside>
      </section>
      <section className="single-ai__surface">
        <SectionTitle title="最近审计日志" meta="可追溯" />
        <div className="single-ai__table">
          {[
            ['12:18', '确认写入', '4.3 售后服务保障', 'Hubert'],
            ['12:10', '一键修复风险', '响应矩阵 2 条风险', '张三'],
            ['11:52', '上传素材', 'ISO27001 证书', '张三'],
          ].map((row) => (
            <div key={row.join('-')} className="single-ai__table-row">
              <strong>{row[0]}</strong>
              <span>{row[1]}</span>
              <span>{row[2]}</span>
              <small>{row[3]}</small>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}): React.ReactElement {
  return (
    <header className="single-ai__page-header">
      <div>
        <p className="single-ai__eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}

function SectionTitle({ title, meta }: { title: string; meta?: string }): React.ReactElement {
  return (
    <div className="single-ai__section-title">
      <strong>{title}</strong>
      {meta && <span>{meta}</span>}
    </div>
  );
}

function TaskItem({ status, title, text }: { status: StepStatus; title: string; text: string }): React.ReactElement {
  return (
    <div className="single-ai__task-item">
      <StatusPill status={status} />
      <strong>{title}</strong>
      <p>{text}</p>
    </div>
  );
}

function ObjectLine({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }): React.ReactElement {
  return (
    <div className="single-ai__object-line">
      <span>{icon}</span>
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
    </div>
  );
}

function ProjectWorkflow({
  activeStepKey,
  onStepChange,
  onBack,
}: {
  activeStepKey: StepKey;
  onStepChange: (step: StepKey) => void;
  onBack: () => void;
}): React.ReactElement {
  const activeStep = useMemo(
    () => projectSteps.find((step) => step.key === activeStepKey) || projectSteps[0],
    [activeStepKey],
  );

  return (
    <main className="single-ai__project">
      <header className="single-ai__project-header">
        <button type="button" className="single-ai__back-button" onClick={onBack}>
          <RightOutlined />
          返回首页
        </button>
        <div>
          <p className="single-ai__eyebrow">Project workflow</p>
          <h1>智慧园区综合治理平台投标</h1>
          <p>项目按真实标书生产依赖串行推进。已有数据的步骤可以跳转，缺前置条件的步骤会说明门禁原因。</p>
        </div>
      </header>

      <section className="single-ai__project-command">
        <span><ThunderboltOutlined /></span>
        <input aria-label="项目内 AI 指令" placeholder="继续生成当前章节，或修复响应矩阵风险" />
        <button type="button">发送</button>
      </section>

      <section className="single-ai__workflow-layout">
        <div className="single-ai__steps" aria-label="项目流程步骤">
          {projectSteps.map((step, index) => {
            const config = statusConfig[step.status];
            return (
              <button
                key={step.key}
                type="button"
                className={`single-ai__step single-ai__step--${config.className} ${activeStepKey === step.key ? 'single-ai__step--selected' : ''}`}
                onClick={() => onStepChange(step.key)}
              >
                <span className="single-ai__step-index">{String(index + 1).padStart(2, '0')}</span>
                <span className="single-ai__step-body">
                  <span className="single-ai__step-title">{step.title}</span>
                  <span className="single-ai__step-summary">{step.summary}</span>
                </span>
                <span className="single-ai__step-state">
                  {config.icon}
                  {config.label}
                </span>
              </button>
            );
          })}
        </div>

        <div className="single-ai__stage">
          <StageHeader activeStep={activeStep} />
          <StageContent stepKey={activeStepKey} onStepChange={onStepChange} />
        </div>
      </section>
    </main>
  );
}

function StageHeader({ activeStep }: { activeStep: ProjectStep }): React.ReactElement {
  return (
    <div className="single-ai__stage-header">
      <span className="single-ai__detail-icon"><FileSearchOutlined /></span>
      <div>
        <p>{activeStep.dataState}</p>
        <h2>{activeStep.title}</h2>
        <span>{activeStep.summary}</span>
      </div>
    </div>
  );
}

function StageContent({ stepKey, onStepChange }: { stepKey: StepKey; onStepChange: (step: StepKey) => void }): React.ReactElement {
  if (stepKey === 'upload') {
    return (
      <section className="single-ai__stage-grid">
        <div className="single-ai__surface single-ai__dropzone">
          <CloudUploadOutlined />
          <strong>拖拽或选择招标文件</strong>
          <p>演示支持 docx / pdf。上传后进入解析确认，真实系统会调用文件解析接口。</p>
          <button type="button" className="single-ai__primary-button" onClick={() => onStepChange('analysis')}>模拟上传完成</button>
        </div>
        <aside className="single-ai__surface">
          <SectionTitle title="已上传文件" meta="3 个文件" />
          <div className="single-ai__object-list">
            <ObjectLine icon={<FileDoneOutlined />} title="招标文件.pdf" text="58 页 · 已提取文本" />
            <ObjectLine icon={<FileDoneOutlined />} title="评分办法.docx" text="12 条评分项 · 已识别" />
            <ObjectLine icon={<FileDoneOutlined />} title="附件清单.xlsx" text="8 项材料需求 · 待匹配" />
          </div>
        </aside>
      </section>
    );
  }

  if (stepKey === 'analysis') {
    return (
      <section className="single-ai__stage-grid">
        <div className="single-ai__surface">
          <SectionTitle title="解析结果" meta="已确认" />
          <div className="single-ai__metric-grid">
            <Metric label="评分项" value="12" />
            <Metric label="废标条款" value="3" />
            <Metric label="材料需求" value="8" />
          </div>
          <div className="single-ai__copy-block">
            <strong>项目概况</strong>
            <p>智慧园区综合治理平台，建设内容包含数据治理、运行监测、服务响应和安全保障。</p>
          </div>
          <button type="button" className="single-ai__primary-button" onClick={() => onStepChange('matrix')}>生成响应矩阵</button>
        </div>
        <aside className="single-ai__surface">
          <SectionTitle title="关键条款" meta="AI 摘要" />
          <div className="single-ai__task-list">
            <TaskItem status="risk" title="7x24 小时响应" text="必须在售后方案中明确承诺。" />
            <TaskItem status="done" title="项目经理资格" text="需提供信息系统项目管理师证书。" />
            <TaskItem status="ready" title="培训服务" text="需覆盖管理员培训和操作手册。" />
          </div>
        </aside>
      </section>
    );
  }

  if (stepKey === 'matrix') {
    return (
      <section className="single-ai__surface">
        <SectionTitle title="响应矩阵" meta="47 条条款 · 2 条风险" />
        <div className="single-ai__table single-ai__table--matrix">
          {matrixRows.map((row) => (
            <div key={row[0]} className="single-ai__table-row">
              <strong>{row[0]}</strong>
              <span>{row[1]}</span>
              <span>{row[2]}</span>
              <StatusPill status={row[4] === 'done' ? 'done' : 'risk'}>{row[3]}</StatusPill>
            </div>
          ))}
        </div>
        <div className="single-ai__action-row">
          <button type="button" className="single-ai__primary-button" onClick={() => onStepChange('draft')}><ThunderboltOutlined />一键修复风险</button>
          <button type="button" className="single-ai__ghost-button">查看证据来源</button>
        </div>
      </section>
    );
  }

  if (stepKey === 'outline') {
    return (
      <section className="single-ai__stage-grid single-ai__stage-grid--wide">
        <div className="single-ai__surface">
          <SectionTitle title="标书目录结构" meta="5 个一级章 · 25 个章节 · 18 章已有正文" />
          <div className="single-ai__outline-toolbar">
            <button type="button" className="single-ai__outline-tool--active">按章节</button>
            <button type="button">按评分项</button>
            <button type="button">只看风险</button>
          </div>
          <div className="single-ai__outline-tree">
            {outlineChapters.map((chapter) => (
              <button
                key={chapter.no}
                type="button"
                className={`${chapter.no === '4.3' ? 'single-ai__outline-active' : ''} single-ai__outline-level-${chapter.level}`}
              >
                <span className="single-ai__outline-main">
                  <strong>{chapter.no}</strong>
                  <span>{chapter.title}</span>
                </span>
                <span className="single-ai__outline-meta">
                  <small>{chapter.score}</small>
                  <small>{chapter.owner}</small>
                  <StatusPill status={chapter.status} />
                </span>
              </button>
            ))}
          </div>
        </div>
        <aside className="single-ai__surface">
          <SectionTitle title="当前章节" meta="4.3 SLA 承诺与闭环管理" />
          <div className="single-ai__chapter-card">
            <div>
              <span>绑定评分项</span>
              <strong>评分项 3.2 售后响应能力</strong>
              <p>要求明确响应时限、服务团队、闭环验收机制，并提供可引用案例。</p>
            </div>
            <div>
              <span>生成依据</span>
              <strong>3 份素材可引用</strong>
              <p>历史 SLA 案例、服务团队清单、运维平台截图。</p>
            </div>
            <div>
              <span>版本状态</span>
              <strong>目录 V4 · 12:18</strong>
              <p>本章标题由“售后服务保障”拆分为 3 个二级章，当前版本可回滚。</p>
            </div>
          </div>
          <div className="single-ai__action-row">
            <button type="button" className="single-ai__primary-button" onClick={() => onStepChange('draft')}><ThunderboltOutlined />生成本章正文</button>
            <button type="button" className="single-ai__ghost-button">查看目录版本</button>
          </div>
        </aside>
      </section>
    );
  }

  if (stepKey === 'draft') {
    return (
      <section className="single-ai__stage-grid single-ai__stage-grid--wide">
        <div className="single-ai__surface single-ai__editor">
          <SectionTitle title="4.3 SLA 承诺与闭环管理" meta="AI 生成中 · 已覆盖 2/3 个要求" />
          <div className="single-ai__generation-status">
            <span>目录</span>
            <strong>4 售后服务保障 / 4.3 SLA 承诺与闭环管理</strong>
            <em>当前输出将写入 V3 草稿</em>
          </div>
          <div className="single-ai__generated-doc">
            {generatedBlocks.map((block) => (
              <article key={block.title} className="single-ai__generated-block">
                <header>
                  <span>{block.label}</span>
                  <strong>{block.title}</strong>
                </header>
                <p>{block.text}</p>
                <small>{block.evidence}</small>
              </article>
            ))}
          </div>
          <div className="single-ai__evidence-box">
            <CheckCircleOutlined />
            <span>评分项 3.2 已补齐响应时限；驻场支持安排仍需负责人确认。</span>
          </div>
          <div className="single-ai__action-row">
            <button type="button" className="single-ai__primary-button" onClick={() => onStepChange('review')}><CheckCircleOutlined />确认写入</button>
            <button type="button" className="single-ai__ghost-button"><ReloadOutlined />重新生成</button>
            <button type="button" className="single-ai__ghost-button">只重写本段</button>
          </div>
        </div>
        <aside className="single-ai__surface">
          <SectionTitle title="生成控制台" meta="提示清晰、动作收敛" />
          <div className="single-ai__prompt-box">
            <strong>当前指令</strong>
            <p>围绕评分项 3.2 生成售后 SLA 承诺，语气正式，必须引用历史案例。</p>
          </div>
          <div className="single-ai__task-list">
            <TaskItem status="done" title="已插入响应承诺" text="2 小时响应和 4 小时到场已写入正文。" />
            <TaskItem status="done" title="已挂接引用材料" text="历史 SLA 案例和服务台值班表已进入引用清单。" />
            <TaskItem status="risk" title="待确认驻场人员" text="缺少可写入正式标书的人员名单。" />
          </div>
        </aside>
      </section>
    );
  }

  if (stepKey === 'review') {
    return (
      <section className="single-ai__stage-grid single-ai__stage-grid--wide">
        <div className="single-ai__surface">
          <SectionTitle title="质量审查与 Diff" meta="三维度检查 · 3 处建议修改" />
          <div className="single-ai__metric-grid">
            <Metric label="响应性" value="92%" />
            <Metric label="合规性" value="通过" />
            <Metric label="一致性" value="1 项" />
          </div>
          <div className="single-ai__review-tabs" aria-label="审查维度">
            <button type="button" className="single-ai__outline-tool--active">响应性</button>
            <button type="button">合规性</button>
            <button type="button">一致性</button>
          </div>
          <div className="single-ai__diff-view">
            {diffRows.map((row, index) => (
              <div key={`${row.type}-${index}`} className={`single-ai__diff-line single-ai__diff-line--${row.type}`}>
                <code>{row.type === 'add' ? '+' : row.type === 'remove' ? '-' : ' '}</code>
                <span>{row.text}</span>
              </div>
            ))}
          </div>
          <div className="single-ai__action-row">
            <button type="button" className="single-ai__primary-button"><CheckCircleOutlined />执行修改并生成 V3</button>
            <button type="button" className="single-ai__ghost-button">仅采纳选中项</button>
            <button type="button" className="single-ai__ghost-button" onClick={() => onStepChange('export')}>进入导出门禁</button>
          </div>
        </div>
        <aside className="single-ai__surface">
          <SectionTitle title="版本管理" meta="修改后可追溯" />
          <div className="single-ai__version-list">
            {versionRows.map((row, index) => (
              <button key={row[0]} type="button" className={index === 0 ? 'single-ai__version-active' : undefined}>
                <span>{row[0]}</span>
                <strong>{row[1]}</strong>
                <small>{row[2]}</small>
                <em>{row[3]}</em>
              </button>
            ))}
          </div>
          <div className="single-ai__task-list">
            <TaskItem status="risk" title="售后服务评分项证据不足" text="AI 已给出 diff 建议，执行后会生成 V3 并保留 V2。" />
            <TaskItem status="done" title="目录层级符合模板" text="章节层级和标题格式均通过。" />
            <TaskItem status="ready" title="可导出批注版" text="审查问题可写入 Word 批注。" />
          </div>
        </aside>
      </section>
    );
  }

  return (
    <section className="single-ai__stage-grid">
      <div className="single-ai__surface">
        <SectionTitle title="导出交付" meta="质量门禁" />
        <div className="single-ai__task-list">
          <TaskItem status="done" title="模板配置完成" text="政府采购技术标模板已绑定。" />
          <TaskItem status="risk" title="评分项证据缺失" text="2 个评分项仍需人工确认。" />
          <TaskItem status="locked" title="正式交付包" text="风险清零后开放下载。" />
        </div>
        <div className="single-ai__action-row">
          <button type="button" className="single-ai__primary-button"><ExportOutlined />导出批注版</button>
          <button type="button" className="single-ai__ghost-button">查看门禁原因</button>
        </div>
      </div>
      <aside className="single-ai__surface">
        <SectionTitle title="交付包预览" meta="3 个文件" />
        <div className="single-ai__object-list">
          <ObjectLine icon={<FileDoneOutlined />} title="正式 Word" text="等待风险清零" />
          <ObjectLine icon={<FileDoneOutlined />} title="批注版 Word" text="可导出" />
          <ObjectLine icon={<FileDoneOutlined />} title="质量报告 PDF" text="可导出" />
        </div>
      </aside>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }): React.ReactElement {
  return (
    <div className="single-ai__metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

const AINativePrototype: React.FC = () => {
  const [view, setView] = useState<PrototypeView>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const viewParam = params.get('view') as PrototypeView | null;
      if (viewParam && ['home', 'projects', 'materials', 'templates', 'settings', 'project'].includes(viewParam)) {
        return viewParam;
      }
      return params.get('mode') === 'project' ? 'project' : 'home';
    }
    return 'home';
  });
  const [activeStepKey, setActiveStepKey] = useState<StepKey>(() => {
    if (typeof window !== 'undefined') {
      const stepParam = new URLSearchParams(window.location.search).get('step') as StepKey | null;
      if (stepParam && projectSteps.some((step) => step.key === stepParam)) {
        return stepParam;
      }
    }
    return 'draft';
  });

  const openProject = (step: StepKey = 'draft') => {
    setActiveStepKey(step);
    setView('project');
  };

  return (
    <div className="single-ai">
      <TopNav view={view} onNavigate={setView} />
      {view === 'home' && <GlobalEntry onOpenProject={() => openProject('draft')} onNavigate={setView} />}
      {view === 'projects' && <ProjectsHub onOpenProject={() => openProject('draft')} />}
      {view === 'materials' && <MaterialsHub />}
      {view === 'templates' && <TemplatesHub onOpenProject={() => openProject('export')} />}
      {view === 'settings' && <SettingsHub />}
      {view === 'project' && (
        <ProjectWorkflow
          activeStepKey={activeStepKey}
          onStepChange={setActiveStepKey}
          onBack={() => setView('home')}
        />
      )}
    </div>
  );
};

export default AINativePrototype;
