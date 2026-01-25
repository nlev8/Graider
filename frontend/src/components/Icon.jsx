import * as LucideIcons from 'lucide-react'

/**
 * Icon component that wraps Lucide React icons
 * Usage: <Icon name="Home" size={24} />
 */
export function Icon({ name, size = 24, className = '', style = {} }) {
  const LucideIcon = LucideIcons[name]

  if (!LucideIcon) {
    console.warn(`Icon "${name}" not found in lucide-react`)
    return null
  }

  return (
    <LucideIcon
      size={size}
      className={className}
      style={{ display: 'inline-flex', ...style }}
    />
  )
}

export default Icon
