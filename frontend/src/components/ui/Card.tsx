import { cn } from '@/lib/utils'

export function Card({
  className,
  children,
}: {
  className?: string
  children: React.ReactNode
}) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-white/10 bg-card/60 backdrop-blur-xl p-5',
        className,
      )}
    >
      {children}
    </div>
  )
}
