/**
 * 批注面板组件
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  ChatBubbleLeftIcon,
  PlusIcon,
  CheckIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { commentApi } from '../services/api';
import type { Comment, CommentCreateRequest } from '../types/comment';

interface CommentPanelProps {
  chapterId: string;
  isOpen: boolean;
  onClose: () => void;
}

const CommentPanel: React.FC<CommentPanelProps> = ({ chapterId, isOpen, onClose }) => {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(false);
  const [showResolved, setShowResolved] = useState(false);
  const [newComment, setNewComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadComments = useCallback(async () => {
    if (!chapterId) return;

    setLoading(true);
    try {
      const response = await commentApi.list(chapterId, showResolved);
      setComments(response.items);
    } catch (error) {
      console.error('加载批注失败:', error);
    } finally {
      setLoading(false);
    }
  }, [chapterId, showResolved]);

  useEffect(() => {
    if (isOpen) {
      loadComments();
    }
  }, [isOpen, loadComments]);

  const handleAddComment = async () => {
    if (!newComment.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const data: CommentCreateRequest = {
        content: newComment.trim(),
      };
      const comment = await commentApi.create(chapterId, data);
      setComments(prev => [comment, ...prev]);
      setNewComment('');
    } catch (error) {
      console.error('添加批注失败:', error);
      alert('添加批注失败，请重试');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResolveComment = async (commentId: string) => {
    try {
      const updatedComment = await commentApi.resolve(commentId);
      setComments(prev =>
        prev.map(c => (c.id === commentId ? updatedComment : c))
      );
    } catch (error) {
      console.error('标记批注失败:', error);
      alert('标记批注失败，请重试');
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    if (!window.confirm('确定要删除这条批注吗？')) return;

    try {
      await commentApi.delete(commentId);
      setComments(prev => prev.filter(c => c.id !== commentId));
    } catch (error) {
      console.error('删除批注失败:', error);
      alert('删除批注失败，请重试');
    }
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (!isOpen) return null;

  return (
    <div className="w-80 bg-white border-l border-gray-200 flex flex-col h-full">
      {/* 头部 */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center">
          <ChatBubbleLeftIcon className="w-5 h-5 text-gray-500 mr-2" />
          <h3 className="font-medium text-gray-900">批注</h3>
          <span className="ml-2 text-xs text-gray-500">({comments.length})</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded"
        >
          <XMarkIcon className="w-5 h-5 text-gray-400" />
        </button>
      </div>

      {/* 添加批注 */}
      <div className="p-3 border-b border-gray-200">
        <textarea
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          placeholder="添加批注..."
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <div className="mt-2 flex justify-end">
          <button
            onClick={handleAddComment}
            disabled={!newComment.trim() || isSubmitting}
            className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            <PlusIcon className="w-4 h-4 mr-1" />
            添加批注
          </button>
        </div>
      </div>

      {/* 筛选 */}
      <div className="px-4 py-2 border-b border-gray-200">
        <label className="inline-flex items-center text-sm text-gray-600">
          <input
            type="checkbox"
            checked={showResolved}
            onChange={(e) => setShowResolved(e.target.checked)}
            className="rounded border-gray-300 text-blue-600 mr-2"
          />
          显示已解决的批注
        </label>
      </div>

      {/* 批注列表 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          </div>
        ) : comments.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            暂无批注
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {comments.map((comment) => (
              <div
                key={comment.id}
                className={`p-3 ${comment.is_resolved ? 'bg-gray-50' : ''}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium text-gray-900">
                        {comment.username}
                      </span>
                      <span className="text-xs text-gray-400">
                        {formatTime(comment.created_at)}
                      </span>
                      {comment.is_resolved && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-700">
                          已解决
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-gray-700 whitespace-pre-wrap">
                      {comment.content}
                    </p>
                    {comment.is_resolved && comment.resolved_by_username && (
                      <p className="mt-1 text-xs text-gray-500">
                        由 {comment.resolved_by_username} 标记为已解决
                      </p>
                    )}
                  </div>
                </div>
                {!comment.is_resolved && (
                  <div className="mt-2 flex items-center space-x-2">
                    <button
                      onClick={() => handleResolveComment(comment.id)}
                      className="inline-flex items-center px-2 py-1 text-xs text-green-600 hover:bg-green-50 rounded"
                    >
                      <CheckIcon className="w-3 h-3 mr-1" />
                      标记已解决
                    </button>
                    <button
                      onClick={() => handleDeleteComment(comment.id)}
                      className="inline-flex items-center px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded"
                    >
                      <TrashIcon className="w-3 h-3 mr-1" />
                      删除
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CommentPanel;
