import React from 'react';
import { Upload, Spin } from 'antd';
import { UploadOutlined } from '@ant-design/icons';

const { Dragger } = Upload;

interface BidFileUploadProps {
  uploading: boolean;
  onUpload: (file: File) => Promise<false>;
}

const BidFileUpload: React.FC<BidFileUploadProps> = ({ uploading, onUpload }) => (
  <>
    <Dragger
      accept=".docx"
      showUploadList={false}
      beforeUpload={onUpload}
      disabled={uploading}
      style={{ padding: '30px 40px' }}
    >
      <p className="ant-upload-drag-icon">
        <UploadOutlined style={{ fontSize: 40, color: '#1890ff' }} />
      </p>
      <p className="ant-upload-text" style={{ fontSize: 15 }}>
        点击或拖拽上传投标文件
      </p>
      <p className="ant-upload-hint" style={{ fontSize: 13 }}>
        仅支持 .docx 格式，文件大小不超过 50MB
      </p>
    </Dragger>
    {uploading && (
      <div style={{ textAlign: 'center', marginTop: 16 }}>
        <Spin tip="正在上传并解析文件..." />
      </div>
    )}
  </>
);

export default BidFileUpload;
