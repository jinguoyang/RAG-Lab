import { ReactNode, TdHTMLAttributes } from 'react';

interface TableProps {
  children: ReactNode;
  className?: string;
}

export function Table({ children, className = '' }: TableProps) {
  return (
    <div className={`bg-ivory border border-border-cream rounded-[12px] overflow-hidden ${className}`}>
      <table className="w-full">
        {children}
      </table>
    </div>
  );
}

interface TableHeaderProps {
  children: ReactNode;
  className?: string;
}

export function TableHeader({ children, className = '' }: TableHeaderProps) {
  return (
    <thead className={`bg-parchment border-b border-border-cream sticky top-0 ${className}`}>
      {children}
    </thead>
  );
}

interface TableBodyProps {
  children: ReactNode;
  className?: string;
}

export function TableBody({ children, className = '' }: TableBodyProps) {
  return (
    <tbody className={className}>
      {children}
    </tbody>
  );
}

interface TableRowProps {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}

export function TableRow({ children, onClick, className = '' }: TableRowProps) {
  const interactiveStyles = onClick ? 'cursor-pointer hover:bg-parchment transition-colors' : '';

  return (
    <tr
      className={`border-b border-border-cream last:border-b-0 h-12 ${interactiveStyles} ${className}`}
      onClick={onClick}
    >
      {children}
    </tr>
  );
}

interface TableHeadProps {
  children: ReactNode;
  className?: string;
}

export function TableHead({ children, className = '' }: TableHeadProps) {
  return (
    <th className={`px-4 py-3 text-left text-sm font-medium text-olive-gray ${className}`}>
      {children}
    </th>
  );
}

interface TableCellProps extends TdHTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
  className?: string;
  mono?: boolean;
}

export function TableCell({ children, className = '', mono = false, ...props }: TableCellProps) {
  return (
    <td className={`px-4 py-3 text-sm text-near-black ${mono ? 'font-mono' : ''} ${className}`} {...props}>
      {children}
    </td>
  );
}
