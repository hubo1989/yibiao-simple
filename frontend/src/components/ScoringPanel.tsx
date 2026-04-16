/**
 * ScoringPanel - 评分标准面板
 * 支持提取、展示、绑定章节、查看覆盖率
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Button,
  Collapse,
  Progress,
  Tag,
  Select,
  Spin,
  Empty,
  message,
  Tooltip,
  Typography,
  Space,
  Divider,
  Alert,
} from 'antd';
import {
  BulbOutlined,
  LinkOutlined,
  WarningOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { scoringApi, outlineApi } from '../services/api';
import type { ScoringCriteriaItem, ScoringCoverageResponse } from '../services/api';
import type { ProjectChapterListResponse } from '../types/chapter';

const { Text, Title } = Typography;
const { Panel } = Collapse;

export interface ScoringPanelProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
}

// 按 category 分组
function groupByCategory(items: ScoringCriteriaItem[]): Record<string, ScoringCriteriaItem[]> {
  const groups: Record<string, ScoringCriteriaItem[]> = {};
  for (const item of items) {
    const cat = item.category || '其他';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(item);
  }
  return groups;
}

// 覆盖率颜色
function coverageColor(rate: number): string {
  if (rate >= 80) return '#52c41a';
  if (rate >= 40) return '#faad14';
  return '#ff4d4f';
}

const ScoringPanel: React.FC<ScoringPanelProps> = ({ projectId, isOpen, onClose }) => {
  const [items, setItems] = useState<ScoringCriteriaItem[]>([]);
  const [coverage, setCoverage] = useState<ScoringCoverageResponse | null>(null);
  const [chapters, setChapters] = useState<ProjectChapterListResponse['chapters']>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isAutoBinding, setIsAutoBinding] = useState(false);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [listData, chaptersData] = await Promise.all([
        scoringApi.list(projectId),
        outlineApi.getProjectChapters(projectId),
      ]);
      setItems(listData);
      setChapters(chaptersData.chapters || []);

      if (listData.length > 0) {
        const cov = await scoringApi.coverage(projectId);
        setCoverage(cov);
      }
    } catch (e) {
      // silently ignore
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (isOpen) void loadData();
  }, [isOpen, loadData]);

  if (!isOpen) return null;

  const handleExtract = async () => {
    setIsExtracting(true);
    try {
      const result = await scoringApi.extract(projectId);
      message.success(`成功提取 ${result.count} 个评分项`);
      await loadData();
    } catch (e: any) {
      message.error(e.message || '提取失败，请重试');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleAutoBind = async () => {
    setIsAutoBinding(true);
    try {
      const result = await scoringApi.autoBind(projectId);
      message.success(`自动绑定完成：${result.bound_count} / ${result.total_count} 个评分项已绑定`);
      await loadData();
    } catch (e: any) {
      message.error(e.message || '自动绑定失败，请重试');
    } finally {
      setIsAutoBinding(false);
    }
  };

  const handleBindChapter = async (scoringId: string, chapterId: string | null) => {
    try {
      await scoringApi.updateItem(projectId, scoringId, { bound_chapter_id: chapterId || undefined });
      setItems(prev =>
        prev.map(it => (it.id === scoringId ? { ...it, bound_chapter_id: chapterId } : it))
      );
      const cov = await scoringApi.coverage(projectId);
      setCoverage(cov);
    } catch (e: any) {
      message.error(e.message || '绑定失败');
    }
  };

  const totalScore = coverage?.total_score ?? items.reduce((s, it) => s + (it.max_score ?? 0), 0);
  const boundScore = coverage?.bound_score ?? 0;
  const unboundScore = coverage?.unbound_score ?? totalScore;
  const coverageRate = coverage?.coverage_rate ?? 0;

  const groups = groupByCategory(items);

  // 章节选择 options
  const chapterOptions = [
    { value: '', label: '（不绑定）' },
    ...chapters.map(ch => ({
      value: ch.id,
      label: `${ch.chapter_number} ${ch.title}`,
    })),
  ];

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, bottom: 0, width: 480,
      background: '#fff', boxShadow: '-2px 0 8px rgba(0,0,0,0.15)',
      zIndex: 1000, overflowY: 'auto', padding: 20,
    }}>
      {/* 标题栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={5} style={{ margin: 0 }}>评分标准</Typography.Title>
        <Button size="small" onClick={onClose}>关闭</Button>
      </div>
      {/* 顶部操作栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<BulbOutlined />}
            loading={isExtracting}
            onClick={handleExtract}
          >
            提取评分标准
          </Button>
          {items.length > 0 && (
            <Button
              icon={<LinkOutlined />}
              loading={isAutoBinding}
              onClick={handleAutoBind}
            >
              自动绑定章节
            </Button>
          )}
          <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading}>
            刷新
          </Button>
        </Space>
      </div>

      {/* 覆盖率摘要 */}
      {items.length > 0 && (
        <div
          style={{
            background: '#f8f9fa',
            borderRadius: 10,
            padding: '14px 18px',
            marginBottom: 16,
            border: '1px solid #e8e8e8',
          }}
        >
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 10 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>技术标总分</Text>
              <div>
                <Text strong style={{ fontSize: 20 }}>{totalScore}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}> 分</Text>
              </div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>已覆盖</Text>
              <div>
                <Text strong style={{ fontSize: 20, color: '#52c41a' }}>{boundScore.toFixed(1)}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}> 分</Text>
              </div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>未覆盖</Text>
              <div>
                <Text strong style={{ fontSize: 20, color: unboundScore > 0 ? '#ff4d4f' : '#52c41a' }}>
                  {unboundScore.toFixed(1)}
                </Text>
                <Text type="secondary" style={{ fontSize: 12 }}> 分</Text>
              </div>
            </div>
          </div>
          <Progress
            percent={Math.round(coverageRate)}
            strokeColor={coverageColor(coverageRate)}
            trailColor="#f0f0f0"
            format={p => `${p}% 覆盖`}
            style={{ marginBottom: 0 }}
          />
          {coverage && coverage.high_score_unbound.length > 0 && (
            <Alert
              style={{ marginTop: 10, padding: '4px 10px' }}
              type="warning"
              showIcon
              message={
                <span>
                  {coverage.high_score_unbound.length} 个高分项（≥8分）尚未绑定章节：
                  {coverage.high_score_unbound.slice(0, 3).map(it => (
                    <Tag color="orange" key={it.id} style={{ marginLeft: 4 }}>
                      {it.item}（{it.max_score}分）
                    </Tag>
                  ))}
                  {coverage.high_score_unbound.length > 3 && <Text type="secondary">...</Text>}
                </span>
              }
            />
          )}
        </div>
      )}

      {/* 评分项列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : items.length === 0 ? (
        <Empty
          description="暂无评分标准，点击「提取评分标准」从招标文件中自动提取"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <Collapse
          defaultActiveKey={Object.keys(groups)}
          style={{ background: 'white' }}
          expandIconPosition="end"
        >
          {Object.entries(groups).map(([cat, catItems]) => (
            <Panel
              key={cat}
              header={
                <Space>
                  <Text strong>{cat}</Text>
                  <Tag color="blue">{catItems.length} 项</Tag>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    共 {catItems.reduce((s, it) => s + (it.max_score ?? 0), 0)} 分
                  </Text>
                </Space>
              }
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {catItems.map(sc => {
                  const isHighScore = (sc.max_score ?? 0) >= 8;
                  const isBound = Boolean(sc.bound_chapter_id);
                  return (
                    <div
                      key={sc.id}
                      style={{
                        borderRadius: 8,
                        border: `1px solid ${isHighScore ? '#ffbb96' : '#f0f0f0'}`,
                        background: isHighScore ? '#fff7f0' : '#fafafa',
                        padding: '10px 14px',
                      }}
                    >
                      {/* 标题行 */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
                        <Text strong style={{ flex: 1, minWidth: 0 }}>
                          {sc.item}
                        </Text>
                        {sc.max_score != null && (
                          <Tag
                            color={isHighScore ? 'volcano' : 'geekblue'}
                            style={{ flexShrink: 0 }}
                          >
                            {sc.max_score} 分
                          </Tag>
                        )}
                        {!isBound && (
                          <Tooltip title="未绑定章节">
                            <Tag icon={<WarningOutlined />} color="warning">未绑定</Tag>
                          </Tooltip>
                        )}
                        {isBound && (
                          <Tag icon={<CheckCircleOutlined />} color="success">已绑定</Tag>
                        )}
                      </div>

                      {/* 评分规则 */}
                      {sc.scoring_rule && (
                        <Text
                          type="secondary"
                          style={{ fontSize: 12, display: 'block', marginBottom: 8, lineHeight: '1.5' }}
                        >
                          {sc.scoring_rule}
                        </Text>
                      )}

                      {/* 关键词 */}
                      {sc.keywords?.length > 0 && (
                        <div style={{ marginBottom: 8 }}>
                          {sc.keywords.map(kw => (
                            <Tag key={kw} style={{ fontSize: 11, marginBottom: 2 }}>{kw}</Tag>
                          ))}
                        </div>
                      )}

                      {/* 绑定章节选择器 */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <LinkOutlined style={{ color: '#8c8c8c', flexShrink: 0 }} />
                        <Select
                          size="small"
                          style={{ flex: 1, minWidth: 200 }}
                          value={sc.bound_chapter_id || ''}
                          options={chapterOptions}
                          placeholder="选择绑定章节"
                          showSearch
                          filterOption={(input, option) =>
                            (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
                          }
                          onChange={(val: string) => handleBindChapter(sc.id, val || null)}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Panel>
          ))}
        </Collapse>
      )}
    </div>
  );
};

export default ScoringPanel;
