/**
 * 项目成员侧边栏组件
 */
import React, { useState, useEffect, useCallback } from 'react';
import { UsersIcon, XMarkIcon, UserCircleIcon } from '@heroicons/react/24/outline';
import { projectApi } from '../services/api';
import type { ProjectMember } from '../types/project';
import { PROJECT_MEMBER_ROLE_LABELS, PROJECT_MEMBER_ROLE_COLORS } from '../types/project';

interface MemberSidebarProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
}

const MemberSidebar: React.FC<MemberSidebarProps> = ({ projectId, isOpen, onClose }) => {
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(false);

  const loadMembers = useCallback(async () => {
    if (!projectId) return;

    setLoading(true);
    try {
      const data = await projectApi.getMembers(projectId);
      setMembers(data);
    } catch (error) {
      console.error('加载成员列表失败:', error);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (isOpen) {
      loadMembers();
    }
  }, [isOpen, loadMembers]);

  const formatJoinedTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  // 按角色分组
  const groupedMembers = members.reduce((acc, member) => {
    const role = member.role;
    if (!acc[role]) {
      acc[role] = [];
    }
    acc[role].push(member);
    return acc;
  }, {} as Record<string, ProjectMember[]>);

  const roleOrder = ['owner', 'editor', 'reviewer'];

  if (!isOpen) return null;

  return (
    <div className="w-64 bg-white border-l border-gray-200 flex flex-col h-full">
      {/* 头部 */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center">
          <UsersIcon className="w-5 h-5 text-gray-500 mr-2" />
          <h3 className="font-medium text-gray-900">项目成员</h3>
          <span className="ml-2 text-xs text-gray-500">({members.length})</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded"
        >
          <XMarkIcon className="w-5 h-5 text-gray-400" />
        </button>
      </div>

      {/* 成员列表 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          </div>
        ) : members.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            暂无成员
          </div>
        ) : (
          <div className="p-3">
            {roleOrder.map((role) => {
              const roleMembers = groupedMembers[role];
              if (!roleMembers || roleMembers.length === 0) return null;

              return (
                <div key={role} className="mb-4">
                  <div className="flex items-center mb-2">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${PROJECT_MEMBER_ROLE_COLORS[role as keyof typeof PROJECT_MEMBER_ROLE_COLORS]}`}>
                      {PROJECT_MEMBER_ROLE_LABELS[role as keyof typeof PROJECT_MEMBER_ROLE_LABELS]}
                    </span>
                    <span className="ml-2 text-xs text-gray-400">
                      {roleMembers.length} 人
                    </span>
                  </div>
                  <div className="space-y-2">
                    {roleMembers.map((member) => (
                      <div
                        key={member.user_id}
                        className="flex items-center p-2 rounded-lg hover:bg-gray-50"
                      >
                        <UserCircleIcon className="w-8 h-8 text-gray-400 mr-2" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {member.username}
                          </p>
                          <p className="text-xs text-gray-500 truncate">
                            加入于 {formatJoinedTime(member.joined_at)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default MemberSidebar;
