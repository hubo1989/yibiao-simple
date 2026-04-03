# 前端应用 - AI写标书助手

基于 React + TypeScript + Ant Design 构建的现代化单页应用。

## 技术栈

| 技术 | 版本 | 说明 |
|------|------|------|
| React | 19.1.1 | 前端框架 |
| TypeScript | 4.9.5 | 类型安全 |
| Ant Design | 5.29.3 | UI 组件库 |
| Ant Design Pro | 2.8.10 | 高级组件 |
| Tailwind CSS | 3.4.17 | 原子化 CSS |
| Axios | 1.11.0 | HTTP 客户端 |
| React Router | 6.30.3 | 路由管理 |

## 项目结构

```
frontend/
├── src/
│   ├── pages/                    # 页面组件
│   │   ├── Login.tsx            # 登录页
│   │   ├── ProjectList.tsx      # 项目列表
│   │   ├── ProjectWorkspace.tsx # 项目工作台
│   │   ├── ContentEdit.tsx      # 内容编辑
│   │   ├── MaterialLibrary.tsx  # 素材库 [新]
│   │   ├── KnowledgeBase.tsx    # 知识库
│   │   └── Admin.tsx            # 管理后台
│   ├── components/               # 可复用组件
│   │   ├── ConfigPanel.tsx      # 配置面板
│   │   ├── StepBar.tsx          # 步骤导航
│   │   ├── CommentPanel.tsx     # 批注面板
│   │   └── IngestionWizard.tsx  # 导入向导 [新]
│   ├── contexts/                 # Context状态管理
│   │   └── AuthContext.tsx      # 认证上下文
│   ├── hooks/                    # React Hooks
│   │   └── useAppState.ts       # 应用状态管理
│   ├── services/                 # API服务
│   │   └── api.ts               # 统一API调用
│   ├── types/                    # TypeScript类型定义
│   │   ├── auth.ts
│   │   ├── project.ts
│   │   ├── material.ts          # 素材类型 [新]
│   │   └── index.ts
│   ├── layouts/                  # 布局组件
│   │   └── BasicLayout.tsx      # 基础布局
│   ├── App.tsx                   # 应用入口
│   └── index.tsx                 # React挂载点
├── public/                       # 静态资源
└── package.json                  # 依赖配置
```

## 可用脚本

### 开发模式

```bash
npm start
```

启动开发服务器，访问 [http://localhost:3000](http://localhost:3000)

### 生产构建

```bash
npm run build
```

将应用构建到 `build/` 目录，优化后的文件可用于生产部署。

### 测试

```bash
npm test
```

启动交互式测试监视器。

---

## 路由结构

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | ProjectList | 项目列表 |
| `/project/:id` | ProjectWorkspace | 项目工作台 |
| `/project/:id/settings` | ProjectSettings | 项目设置 |
| `/project/:id/review` | BidReview | 标书评审 |
| `/knowledge` | KnowledgeBase | 知识库 |
| `/materials` | MaterialLibrary | 素材库 |
| `/admin` | Admin | 管理后台 |

---

## API 集成

前端通过 `services/api.ts` 与后端通信：

```typescript
// 示例：调用项目API
import { projectApi } from '../services/api';

const projects = await projectApi.list();
```

### API 模块

- `authApi` - 认证相关
- `projectApi` - 项目管理
- `materialApi` - 素材库
- `chapterApi` - 章节操作
- `versionApi` - 版本控制
- `commentApi` - 批注管理
- `consistencyApi` - 一致性检查
- `adminApi` - 管理后台
- `promptApi` - 提示词配置

---

## 状态管理

### 认证状态 (AuthContext)

```typescript
const { user, login, logout } = useAuth();
```

### 应用状态 (useAppState)

```typescript
const { currentStep, outlineData, projectOverview } = useAppState();
```

---

## 开发注意事项

1. **类型安全**：所有组件使用 TypeScript，严格类型检查
2. **组件风格**：函数组件 + Hooks，不使用类组件
3. **状态管理**：优先使用 Context API，复杂场景考虑状态管理库
4. **错误处理**：API 调用需要 try-catch，显示用户友好的错误提示
5. **代码风格**：遵循项目 ESLint 配置

---

## 环境变量

创建 `.env` 文件配置环境变量：

```bash
REACT_APP_API_URL=http://localhost:8000
```

---

## 更多资源

- [React 文档](https://react.dev)
- [TypeScript 文档](https://www.typescriptlang.org)
- [Ant Design 文档](https://ant.design)
- [Tailwind CSS 文档](https://tailwindcss.com)
