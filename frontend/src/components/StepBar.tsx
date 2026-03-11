import React from 'react';

interface StepBarProps {
  steps: string[];
  currentStep: number;
  className?: string;
  variant?: 'default' | 'inline';
  onStepClick?: (stepIndex: number) => void;
  isStepEnabled?: (stepIndex: number) => boolean;
}

const StepBar: React.FC<StepBarProps> = ({
  steps,
  currentStep,
  className,
  variant = 'default',
  onStepClick,
  isStepEnabled,
}) => {
  const inline = variant === 'inline';

  return (
    <div
      className={className}
      style={{
        padding: inline ? 0 : '12px 16px',
        flex: 1,
        maxWidth: inline ? 'none' : 800,
        margin: inline ? 0 : '0 auto',
        width: '100%',
      }}
    >
      <div className="grid gap-3 md:grid-cols-3">
        {steps.map((step, index) => {
          const active = index === currentStep;
          const enabled = isStepEnabled ? isStepEnabled(index) : true;
          const stateLabel = active ? '当前步骤' : enabled ? '点击切换' : '待上一阶段完成';

          return (
            <button
              key={step}
              type="button"
              disabled={!enabled}
              onClick={() => {
                if (enabled) {
                  onStepClick?.(index);
                }
              }}
              className={[
                'group relative w-full overflow-hidden rounded-[22px] border px-5 py-4 text-left transition-all',
                active
                  ? 'border-sky-500 bg-[linear-gradient(135deg,#f5fbff_0%,#e9f5ff_100%)] shadow-[0_18px_35px_-28px_rgba(14,116,214,0.8)]'
                  : enabled
                    ? 'border-slate-200 bg-white hover:-translate-y-0.5 hover:border-sky-300 hover:bg-sky-50/50 hover:shadow-[0_18px_30px_-28px_rgba(15,23,42,0.7)]'
                    : 'cursor-not-allowed border-slate-200 bg-slate-50/90 opacity-70',
              ].join(' ')}
            >
              <div className="flex items-center gap-3">
                <span
                  className={[
                    'flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-colors',
                    active
                      ? 'bg-sky-500 text-white shadow-[0_10px_20px_-12px_rgba(14,116,214,0.95)]'
                      : enabled
                        ? 'bg-slate-100 text-slate-700 group-hover:bg-sky-100 group-hover:text-sky-700'
                        : 'bg-slate-200 text-slate-400',
                  ].join(' ')}
                >
                  {index + 1}
                </span>

                <span className="min-w-0 flex-1">
                  <span
                    className={[
                      'block truncate text-sm font-semibold',
                      active ? 'text-sky-800' : 'text-slate-800',
                    ].join(' ')}
                  >
                    {step}
                  </span>
                  <span
                    className={[
                      'mt-1 block text-xs',
                      active
                        ? 'text-sky-700'
                        : enabled
                          ? 'text-slate-500'
                          : 'text-slate-400',
                    ].join(' ')}
                  >
                    {stateLabel}
                  </span>
                </span>
              </div>

              {active ? (
                <span className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-[linear-gradient(90deg,#0ea5e9_0%,#38bdf8_100%)]" />
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default StepBar;
