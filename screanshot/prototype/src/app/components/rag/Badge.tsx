import { ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'success' | 'error' | 'warning' | 'info' | 'queued' | 'running' | 'active' | 'inactive';
  icon?: ReactNode;
  className?: string;
}

export function Badge({ children, variant = 'default', icon, className = '' }: BadgeProps) {
  const baseStyles = 'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium';

  const variantStyles = {
    default: 'bg-border-warm text-olive-gray border border-border-cream',
    success: 'bg-[#e8f3ed] text-success-green border border-[#d0e7d9]',
    error: 'bg-[#fce8e8] text-error-red border border-[#f5d0d0]',
    warning: 'bg-[#fdf5eb] text-[#a67c47] border border-[#f4e5d0]',
    info: 'bg-[#edf4f7] text-info-blue border border-[#d6e7ef]',
    queued: 'bg-border-cream text-stone-gray border border-border-warm',
    running: 'bg-[#fef3ef] text-terracotta border border-[#f5ddd3]',
    active: 'bg-[#fef3ef] text-terracotta border border-terracotta',
    inactive: 'bg-transparent text-stone-gray border border-border-warm'
  };

  return (
    <span className={`${baseStyles} ${variantStyles[variant]} ${className}`}>
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {children}
    </span>
  );
}

interface StatusBadgeProps {
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled' | 'partial' | 'active' | 'inactive';
  className?: string;
}

export function StatusBadge({ status, className = '' }: StatusBadgeProps) {
  const statusConfig = {
    queued: { variant: 'queued' as const, icon: '○', label: 'Queued' },
    running: { variant: 'running' as const, icon: '◐', label: 'Running' },
    success: { variant: 'success' as const, icon: '✓', label: 'Success' },
    failed: { variant: 'error' as const, icon: '✕', label: 'Failed' },
    cancelled: { variant: 'inactive' as const, icon: '−', label: 'Cancelled' },
    partial: { variant: 'warning' as const, icon: '!', label: 'Partial' },
    active: { variant: 'active' as const, icon: '●', label: 'Active' },
    inactive: { variant: 'inactive' as const, icon: '○', label: 'Inactive' }
  };

  const config = statusConfig[status];

  return (
    <Badge variant={config.variant} icon={<span>{config.icon}</span>} className={className}>
      {config.label}
    </Badge>
  );
}
