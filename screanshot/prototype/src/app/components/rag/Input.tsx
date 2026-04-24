import { InputHTMLAttributes, forwardRef } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className = '', ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block mb-2 text-sm font-medium text-near-black">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`
            w-full px-3 py-2
            bg-ivory border border-border-cream rounded-[10px]
            text-near-black placeholder:text-stone-gray
            focus:outline-none focus:ring-2 focus:ring-focus-blue focus:border-transparent
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors
            ${error ? 'border-error-red focus:ring-error-red' : ''}
            ${className}
          `}
          {...props}
        />
        {error && (
          <p className="mt-1 text-sm text-error-red">{error}</p>
        )}
        {helperText && !error && (
          <p className="mt-1 text-sm text-stone-gray">{helperText}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
