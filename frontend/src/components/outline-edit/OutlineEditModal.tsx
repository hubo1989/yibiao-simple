import React from 'react';
import { Modal, Form, Input } from 'antd';

interface OutlineEditModalProps {
  visible: boolean;
  title: string;
  description: string;
  onTitleChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onOk: () => void;
  onCancel: () => void;
}

const OutlineEditModal: React.FC<OutlineEditModalProps> = ({
  visible,
  title,
  description,
  onTitleChange,
  onDescriptionChange,
  onOk,
  onCancel,
}) => (
  <Modal
    title="编辑目录项"
    open={visible}
    onOk={onOk}
    onCancel={onCancel}
    okText="保存"
    cancelText="取消"
  >
    <Form layout="vertical">
      <Form.Item label="目录标题">
        <Input
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="请输入目录标题"
        />
      </Form.Item>
      <Form.Item label="目录描述">
        <Input.TextArea
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          rows={4}
          placeholder="请输入目录描述"
        />
      </Form.Item>
    </Form>
  </Modal>
);

export default OutlineEditModal;
