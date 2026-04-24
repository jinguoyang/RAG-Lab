import { ReactNode } from 'react';

interface AlertProps {
  children: ReactNode;
  variant?: 'info' | 'success' | 'warning' | 'error' | 'permission';
  title?: string;
  icon?: ReactNode;
  onClose?: () => void;
  className?: string;
}

export function Alert({
  children,
  variant = 'info',
  title,
  icon,
  onClose,
  className = ''
}: AlertProps) {
  const variantStyles = {
    info: 'bg-[#edf4f7] border-info-blue text-info-blue',
    success: 'bg-[#e8f3ed] border-success-green text-success-green',
    warning: 'bg-[#fdf5eb] border-[#a67c47] text-[#a67c47]',
    error: 'bg-[#fce8e8] border-error-red text-error-red',
    permission: 'bg-[#fdf5eb] border-[#a67c47] text-[#a67c47]'
  };

  const defaultIcons = {
    info: 'ⓘ',
    success: '✓',
    warning: '!',
    error: '✕',
    permission: '🔒'
  };

  const displayIcon = icon || defaultIcons[variant];

  return (
    <div
      className={`
        flex gap-3 p-4 rounded-[10px] border-l-4
        ${variantStyles[variant]}
        ${className}
      `}
    >
      {displayIcon && (
        <div className="flex-shrink-0 text-lg">
          {displayIcon}
        </div>
      )}

      <div className="flex-1">
        {title && (
          <h4 className="mb-1 font-medium">{title}</h4>
        )}
        <div className="text-sm text-near-black">
          {children}
        </div>
      </div>

      {onClose && (
        <button
          onClick={onClose}
          className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-[6px] hover:bg-black/10 transition-colors"
        >
          ✕
        </button>
      )}
    </div>
  );
}
