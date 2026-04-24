import { ReactNode, ButtonHTMLAttributes } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles = 'inline-flex items-center justify-center rounded-[10px] transition-colors focus:outline-none focus:ring-2 focus:ring-focus-blue focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';

  const variantStyles = {
    primary: 'bg-terracotta text-white hover:bg-[#b35839] active:bg-[#a04e31]',
    secondary: 'bg-olive-gray text-white hover:bg-[#4f4e4a] active:bg-[#454440]',
    outline: 'border border-border-warm bg-transparent text-near-black hover:bg-border-cream active:bg-border-warm',
    ghost: 'bg-transparent text-near-black hover:bg-border-cream active:bg-border-warm',
    destructive: 'bg-error-red text-white hover:bg-[#a02d2d] active:bg-[#8c2727]'
  };

  const sizeStyles = {
    sm: 'h-8 px-3 text-sm',
    md: 'h-10 px-4 text-base',
    lg: 'h-12 px-6 text-base'
  };

  return (
    <button
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
