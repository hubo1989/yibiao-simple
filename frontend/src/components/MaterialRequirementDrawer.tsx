import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Button, Drawer, Empty, List, Select, Space, Tag, Typography, message } from 'antd';
import { materialApi, outlineApi } from '../services/api';
import type { MaterialMatchCandidate, MaterialRequirement } from '../types/material';
import { getErrorMessage } from '../utils/error';

interface MaterialRequirementDrawerProps {
  open: boolean;
  projectId: string;
  onClose: () => void;
}

const MaterialRequirementDrawer: React.FC<MaterialRequirementDrawerProps> = ({ open, projectId, onClose }) => {
  const [requirements, setRequirements] = useState<MaterialRequirement[]>([]);
  const [selectedRequirementId, setSelectedRequirementId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<MaterialMatchCandidate[]>([]);
  const [chapters, setChapters] = useState<{ id: string; chapter_number: string; title: string }[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState<string>();
  const [selectedAssetId, setSelectedAssetId] = useState<string>();
  const [loading, setLoading] = useState(false);

  const selectedRequirement = useMemo(
    () => requirements.find((item) => item.id === selectedRequirementId) || null,
    [requirements, selectedRequirementId]
  );

  const loadRequirements = useCallback(async () => {
    setLoading(true);
    try {
      const [reqs, chapterResponse] = await Promise.all([
        materialApi.listRequirements(projectId),
        outlineApi.getProjectChapters(projectId),
      ]);
      setRequirements(reqs);
      setChapters(chapterResponse.chapters.map((chapter) => ({
        id: chapter.id,
        chapter_number: chapter.chapter_number,
        title: chapter.title,
      })));
      if (reqs[0]) {
        setSelectedRequirementId(reqs[0].id);
      }
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '加载材料需求失败'));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (open) {
      void loadRequirements();
    }
  }, [loadRequirements, open]);

  useEffect(() => {
    if (!selectedRequirementId) {
      setCandidates([]);
      return;
    }
    void (async () => {
      try {
        const nextCandidates = await materialApi.matchRequirement(projectId, selectedRequirementId);
        setCandidates(nextCandidates);
        setSelectedAssetId(nextCandidates[0]?.asset_id);
      } catch (error: unknown) {
        message.error(getErrorMessage(error, '获取候选素材失败'));
      }
    })();
  }, [projectId, selectedRequirementId]);

  const handleAnalyze = async () => {
    try {
      const reqs = await materialApi.analyzeRequirements(projectId);
      setRequirements(reqs);
      if (reqs[0]) {
        setSelectedRequirementId(reqs[0].id);
      }
      message.success('已重新提取材料需求');
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '提取材料需求失败'));
    }
  };

  const handleCreateBinding = async () => {
    if (!selectedRequirementId || !selectedAssetId || !selectedChapterId) {
      message.warning('请先选择需求、候选素材和目标章节');
      return;
    }
    const selectedCandidate = candidates.find((item) => item.asset_id === selectedAssetId);
    try {
      const updatedRequirement = await materialApi.confirmMatch(projectId, selectedRequirementId, selectedAssetId);
      const binding = await materialApi.createBinding(projectId, selectedChapterId, {
        material_requirement_id: selectedRequirementId,
        material_asset_id: selectedAssetId,
        caption: selectedCandidate?.asset?.name || updatedRequirement.requirement_name,
        anchor_type: 'section_end',
        display_mode: 'image',
      });
      message.success(`绑定成功，正文占位标记： [INSERT_MATERIAL:${binding.id}]`);
      await loadRequirements();
    } catch (error: unknown) {
      message.error(getErrorMessage(error, '创建绑定失败'));
    }
  };

  return (
    <Drawer
      title="材料需求与章节绑定"
      open={open}
      width={1080}
      onClose={onClose}
      extra={<Button onClick={() => void handleAnalyze()}>重新分析</Button>}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr 0.9fr', gap: 16 }}>
        <div>
          <Typography.Title level={5}>材料需求</Typography.Title>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="从项目招标文件中抽取需要提交的附件材料"
          />
          <List
            bordered
            loading={loading}
            locale={{ emptyText: <Empty description="还没有材料需求，先点击“重新分析”" /> }}
            dataSource={requirements}
            renderItem={(item) => (
              <List.Item
                onClick={() => setSelectedRequirementId(item.id)}
                style={{ cursor: 'pointer', background: item.id === selectedRequirementId ? '#eff6ff' : undefined }}
              >
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Space wrap>
                    <Typography.Text strong>{item.requirement_name}</Typography.Text>
                    <Tag>{item.status}</Tag>
                  </Space>
                  <Typography.Text type="secondary">{item.requirement_text}</Typography.Text>
                </Space>
              </List.Item>
            )}
          />
        </div>

        <div>
          <Typography.Title level={5}>候选素材</Typography.Title>
          <List
            bordered
            locale={{ emptyText: <Empty description="选择材料需求后查看候选素材" /> }}
            dataSource={candidates}
            renderItem={(item) => (
              <List.Item
                onClick={() => setSelectedAssetId(item.asset_id)}
                style={{ cursor: 'pointer', background: item.asset_id === selectedAssetId ? '#fef3c7' : undefined }}
              >
                <Space direction="vertical" size={6} style={{ width: '100%' }}>
                  <Space wrap>
                    <Typography.Text strong>{item.asset?.name || item.asset_id}</Typography.Text>
                    <Tag color="blue">得分 {Math.round(item.score)}</Tag>
                  </Space>
                  <Space wrap>
                    {item.matched_reasons.map((reason) => (
                      <Tag key={reason}>{reason}</Tag>
                    ))}
                  </Space>
                </Space>
              </List.Item>
            )}
          />
        </div>

        <div>
          <Typography.Title level={5}>落位章节</Typography.Title>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Select
              placeholder="选择目标章节"
              value={selectedChapterId}
              onChange={setSelectedChapterId}
              options={chapters.map((chapter) => ({
                label: `${chapter.chapter_number} ${chapter.title}`,
                value: chapter.id,
              }))}
            />
            <Alert
              type="warning"
              showIcon
              message="绑定完成后，在正文中插入生成的占位标记即可导出渲染"
            />
            <Button type="primary" onClick={() => void handleCreateBinding()}>
              确认匹配并创建绑定
            </Button>
            {selectedRequirement ? (
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                当前需求：{selectedRequirement.requirement_name}
              </Typography.Paragraph>
            ) : null}
          </Space>
        </div>
      </div>
    </Drawer>
  );
};

export default MaterialRequirementDrawer;
