import { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  breadcrumbs?: { label: string; href?: string }[];
  actions?: ReactNode;
  contextLabels?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  contextLabels,
  className = ''
}: PageHeaderProps) {
  return (
    <div className={`bg-ivory border-b border-border-cream px-8 py-6 ${className}`}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex items-center gap-2 mb-3 text-sm text-stone-gray">
          {breadcrumbs.map((crumb, index) => (
            <div key={index} className="flex items-center gap-2">
              {index > 0 && <span>/</span>}
              {crumb.href ? (
                <a href={crumb.href} className="hover:text-near-black transition-colors">
                  {crumb.label}
                </a>
              ) : (
                <span className="text-near-black">{crumb.label}</span>
              )}
            </div>
          ))}
        </nav>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <h1 className="font-serif mb-2">{title}</h1>
          {description && (
            <p className="text-olive-gray">{description}</p>
          )}
        </div>

        <div className="flex items-center gap-3">
          {contextLabels && <div className="flex items-center gap-2">{contextLabels}</div>}
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      </div>
    </div>
  );
}
