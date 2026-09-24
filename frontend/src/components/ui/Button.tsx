import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:pointer-events-none',
        size === 'sm' && 'h-8 px-3 text-xs',
        size === 'md' && 'h-10 px-4 text-sm',
        size === 'lg' && 'h-11 px-6 text-base',
        variant === 'primary' && 'bg-accent text-white hover:bg-accent/90',
        variant === 'secondary' && 'bg-white/5 text-white/80 hover:bg-white/10 border border-white/10',
        variant === 'danger' && 'bg-danger/90 text-white hover:bg-danger',
        variant === 'outline' && 'bg-transparent text-white/70 border border-white/10 hover:bg-white/5',
        variant === 'ghost' && 'bg-transparent text-white/50 hover:bg-white/5',
        className,
      )}
      {...props}
    />
  ),
)
Button.displayName = 'Button'
