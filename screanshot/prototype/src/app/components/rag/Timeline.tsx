import { ReactNode } from 'react';
import { StatusBadge } from './Badge';

interface TimelineItem {
  id: string;
  status: 'queued' | 'running' | 'success' | 'failed' | 'cancelled' | 'partial';
  title: string;
  description?: string;
  timestamp?: string;
  duration?: string;
  operator?: string;
  details?: ReactNode;
  isExpanded?: boolean;
}

interface TimelineProps {
  items: TimelineItem[];
  onItemClick?: (id: string) => void;
  className?: string;
}

export function Timeline({ items, onItemClick, className = '' }: TimelineProps) {
  return (
    <div className={`space-y-0 ${className}`}>
      {items.map((item, index) => (
        <TimelineItemComponent
          key={item.id}
          item={item}
          isLast={index === items.length - 1}
          onClick={() => onItemClick?.(item.id)}
        />
      ))}
    </div>
  );
}

interface TimelineItemComponentProps {
  item: TimelineItem;
  isLast: boolean;
  onClick?: () => void;
}

function TimelineItemComponent({ item, isLast, onClick }: TimelineItemComponentProps) {
  const hasInteraction = onClick || item.details;

  return (
    <div className="relative flex gap-4">
      {/* Timeline line */}
      <div className="relative flex flex-col items-center">
        <div className={`
          w-3 h-3 rounded-full border-2 flex-shrink-0 mt-1.5
          ${item.status === 'success' ? 'bg-success-green border-success-green' : ''}
          ${item.status === 'failed' ? 'bg-error-red border-error-red' : ''}
          ${item.status === 'running' ? 'bg-terracotta border-terracotta' : ''}
          ${item.status === 'queued' ? 'bg-transparent border-stone-gray' : ''}
          ${item.status === 'cancelled' ? 'bg-transparent border-stone-gray' : ''}
          ${item.status === 'partial' ? 'bg-warning-amber border-warning-amber' : ''}
        `} />
        {!isLast && (
          <div className="w-0.5 flex-1 bg-border-warm mt-1" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-6">
        <div
          className={`${hasInteraction ? 'cursor-pointer hover:bg-parchment' : ''} -mx-2 px-2 py-1 rounded-[8px] transition-colors`}
          onClick={onClick}
        >
          <div className="flex items-start justify-between gap-4 mb-2">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-medium text-near-black">{item.title}</span>
                <StatusBadge status={item.status} />
              </div>
              {item.description && (
                <p className="text-sm text-olive-gray">{item.description}</p>
              )}
            </div>
            <div className="flex flex-col items-end gap-1 text-sm text-stone-gray">
              {item.duration && <span>{item.duration}</span>}
              {item.timestamp && <span>{item.timestamp}</span>}
            </div>
          </div>

          {item.operator && (
            <p className="text-xs text-stone-gray">by {item.operator}</p>
          )}

          {item.isExpanded && item.details && (
            <div className="mt-3 pt-3 border-t border-border-cream">
              {item.details}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
