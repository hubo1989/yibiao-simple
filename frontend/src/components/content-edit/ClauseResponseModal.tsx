import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Modal, Space, Alert, Button, Typography, Input, Card, Spin } from 'antd';
import type { ClauseResponseResult } from '../../types/bid';

interface ClauseResponseModalProps {
  visible: boolean;
  clauseText: string;
  knowledgeContext: string;
  isLoading: boolean;
  result: ClauseResponseResult | null;
  onClauseTextChange: (text: string) => void;
  onKnowledgeContextChange: (text: string) => void;
  onGenerate: () => void;
  onCopy: () => void;
  onClose: () => void;
}

const ClauseResponseModal: React.FC<ClauseResponseModalProps> = ({
  visible,
  clauseText,
  knowledgeContext,
  isLoading,
  result,
  onClauseTextChange,
  onKnowledgeContextChange,
  onGenerate,
  onCopy,
  onClose,
}) => (
  <Modal
    title="条款逐条响应"
    open={visible}
    width={860}
    onCancel={onClose}
    footer={[
      result ? (
        <Button key="copy" onClick={onCopy}>
          复制结果
        </Button>
      ) : null,
      <Button key="close" onClick={onClose}>
        关闭
      </Button>,
      <Button key="generate" type="primary" loading={isLoading} onClick={onGenerate}>
        {result ? '重新生成' : '生成响应'}
      </Button>,
    ]}
  >
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <div>
        <Typography.Text strong>技术参数或条款原文</Typography.Text>
        <Input.TextArea
          rows={6}
          value={clauseText}
          onChange={(e) => onClauseTextChange(e.target.value)}
          placeholder="请输入需要逐条响应的技术参数、技术条款或服务要求原文"
          style={{ marginTop: 8 }}
        />
      </div>

      <div>
        <Typography.Text strong>补充知识上下文（可选）</Typography.Text>
        <Input.TextArea
          rows={4}
          value={knowledgeContext}
          onChange={(e) => onKnowledgeContextChange(e.target.value)}
          placeholder="可补充企业能力、产品参数、实施边界等信息，帮助生成更贴合项目的响应内容"
          style={{ marginTop: 8 }}
        />
      </div>

      {isLoading ? (
        <div style={{ padding: '32px 0', textAlign: 'center' }}>
          <Spin size="large" />
        </div>
      ) : result ? (
        <Card size="small" title="生成结果">
          <div className="markdown-body">
            <ReactMarkdown>{result.content}</ReactMarkdown>
          </div>
        </Card>
      ) : (
        <Alert
          type="info"
          showIcon
          message="输入条款后点击「生成响应」"
          description="系统会输出可直接用于技术标正文或条款响应表的逐条响应内容。"
        />
      )}
    </Space>
  </Modal>
);

export default ClauseResponseModal;
