import { ReactNode, useEffect } from 'react';

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  children: ReactNode;
  title?: string;
  width?: '480px' | '560px' | '640px';
  className?: string;
}

export function Drawer({
  isOpen,
  onClose,
  children,
  title,
  width = '560px',
  className = ''
}: DrawerProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-near-black/40 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={`fixed right-0 top-0 bottom-0 bg-ivory border-l border-border-cream shadow-lg z-50 flex flex-col ${className}`}
        style={{ width }}
      >
        {/* Header */}
        {title && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-border-cream">
            <h3 className="font-serif">{title}</h3>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-[8px] hover:bg-border-cream transition-colors text-olive-gray"
            >
              ✕
            </button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </>
  );
}

interface DrawerSectionProps {
  children: ReactNode;
  title?: string;
  className?: string;
}

export function DrawerSection({ children, title, className = '' }: DrawerSectionProps) {
  return (
    <div className={`px-6 py-4 border-b border-border-cream last:border-b-0 ${className}`}>
      {title && (
        <h4 className="mb-3 text-olive-gray">{title}</h4>
      )}
      {children}
    </div>
  );
}
