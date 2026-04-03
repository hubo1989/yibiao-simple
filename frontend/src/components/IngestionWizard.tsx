import React from 'react';
import { Modal, Empty } from 'antd';

interface IngestionWizardProps {
  visible: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const IngestionWizard: React.FC<IngestionWizardProps> = ({ visible, onClose, onSuccess }) => {
  return (
    <Modal
      title="从历史标书导入"
      open={visible}
      onCancel={onClose}
      footer={null}
      width={640}
    >
      <Empty description="功能开发中" />
    </Modal>
  );
};

export default IngestionWizard;
