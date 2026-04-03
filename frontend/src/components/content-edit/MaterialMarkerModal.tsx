import React from 'react';
import { Modal, Space, Alert, Input } from 'antd';
import type { ChapterMaterialBinding } from '../../types/material';

interface MaterialMarkerModalProps {
  visible: boolean;
  target: { chapterNumber: string; title: string } | null;
  selectedBindingId: string;
  bindings: ChapterMaterialBinding[];
  onSelectBinding: (id: string) => void;
  onOk: () => void;
  onCancel: () => void;
}

const MaterialMarkerModal: React.FC<MaterialMarkerModalProps> = ({
  visible,
  target,
  selectedBindingId,
  bindings,
  onSelectBinding,
  onOk,
  onCancel,
}) => (
  <Modal
    title={target ? `插入素材：${target.chapterNumber} ${target.title}` : '插入素材'}
    open={visible}
    onCancel={onCancel}
    onOk={onOk}
    okText="插入标记"
  >
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Alert
        type="info"
        showIcon
        message="选择一个当前章节的素材绑定"
        description="插入后会写入 [INSERT_MATERIAL:binding_id] 标记，Word 导出时会自动渲染素材块。"
      />
      <Input.Group compact>
        <Input
          readOnly
          style={{ width: '100%' }}
          value={selectedBindingId ? `[INSERT_MATERIAL:${selectedBindingId}]` : ''}
          placeholder="请先选择素材绑定"
        />
      </Input.Group>
      <select
        value={selectedBindingId}
        onChange={(event) => onSelectBinding(event.target.value)}
        style={{ width: '100%', minHeight: 40, borderRadius: 8, border: '1px solid #d9d9d9', padding: '0 12px' }}
      >
        <option value="">请选择素材绑定</option>
        {bindings.map((binding) => (
          <option key={binding.id} value={binding.id}>
            {binding.material_asset?.name || binding.caption || binding.id}
          </option>
        ))}
      </select>
    </Space>
  </Modal>
);

export default MaterialMarkerModal;
