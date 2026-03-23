import React from 'react';
import { ArrowLeftOutlined } from '@ant-design/icons';

interface ContentPageHeaderProps {
  title: string;
  onBack: () => void;
  eyebrow?: string;
  description?: string;
  backLabel?: string;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  variant?: 'card' | 'flush';
}

const ContentPageHeader: React.FC<ContentPageHeaderProps> = ({
  title,
  onBack,
  eyebrow,
  description,
  backLabel = '返回',
  actions,
  footer,
  variant = 'card',
}) => {
  const isFlush = variant === 'flush';

  return (
    <section
      className={
        isFlush
          ? 'bg-white'
          : 'overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm'
      }
    >
      <div
        className={
          isFlush
            ? 'grid gap-8 py-6 lg:grid-cols-[148px_minmax(0,1fr)] lg:py-7'
            : 'grid gap-8 px-6 py-6 lg:grid-cols-[148px_minmax(0,1fr)] lg:px-8 lg:py-8'
        }
      >
        <div className="flex items-start lg:justify-start">
          <button
            onClick={onBack}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:border-slate-300 hover:text-slate-900"
          >
            <ArrowLeftOutlined />
            {backLabel}
          </button>
        </div>

        <div className="space-y-5 min-w-0">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="min-w-0">
              {eyebrow ? (
                <p className="mb-2 text-sm font-medium text-slate-500">{eyebrow}</p>
              ) : null}
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">{title}</h1>
              {description ? (
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>
              ) : null}
            </div>

            {actions ? (
              <div className="flex flex-wrap items-center gap-3">{actions}</div>
            ) : null}
          </div>

          {footer ? (
            <div className={isFlush ? 'border-t border-slate-200 pt-5' : 'border-t border-slate-200 pt-4'}>
              {footer}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
};

export default ContentPageHeader;
