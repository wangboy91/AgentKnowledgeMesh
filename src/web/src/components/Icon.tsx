/**
 * Icon · 内联 SVG 图标
 * - 业务区不要直接用 emoji;emoji 只允许出现在 i18n 文案中
 * - 所有 icon 接收 size / className / title(可访问性)
 */
import type { SVGProps } from 'react'

type IconProps = Omit<SVGProps<SVGSVGElement>, 'children'> & {
  size?: number | string
  title?: string
}

function svgBase(props: IconProps) {
  const { size = 16, title, ...rest } = props
  return {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.75,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': title ? undefined : true,
    role: title ? 'img' : undefined,
    ...rest,
    children: title ? <title>{title}</title> : undefined,
  }
}

export function SunIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  )
}

export function MoonIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" />
    </svg>
  )
}

export function DashboardIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  )
}

export function BookIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14Z" />
      <path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5H6.5A2.5 2.5 0 0 0 4 19.5Z" />
    </svg>
  )
}

export function GlobeIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </svg>
  )
}

export function SettingsIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </svg>
  )
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  )
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}

export function FolderIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />
    </svg>
  )
}

export function FolderOpenIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H3V7Z" />
      <path d="M3 10h18l-2 7a2 2 0 0 1-2 1.5H5A2 2 0 0 1 3 17V10Z" />
    </svg>
  )
}

export function FileIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z" />
      <path d="M14 3v6h6" />
    </svg>
  )
}

export function HomeIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="m3 11 9-8 9 8v9a2 2 0 0 1-2 2h-4v-7h-6v7H5a2 2 0 0 1-2-2v-9Z" />
    </svg>
  )
}

export function SearchIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  )
}

export function SparkleIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M12 3 14 8.5 20 10.5 14 12.5 12 18 10 12.5 4 10.5 10 8.5Z" />
      <path d="M19 16v3M17.5 17.5h3" />
    </svg>
  )
}

export function EditIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M4 20h4l11-11-4-4L4 16v4Z" />
      <path d="m14 6 4 4" />
    </svg>
  )
}

export function CopyIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
    </svg>
  )
}

export function CheckIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="m5 12 5 5L20 7" />
    </svg>
  )
}

export function ClockIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  )
}

export function BanIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="m5 5 14 14" />
    </svg>
  )
}

export function HourglassIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M6 3h12M6 21h12" />
      <path d="M7 3 17 3l-1 4a6 6 0 0 1-2 4v2a6 6 0 0 1 2 4l1 4H7l1-4a6 6 0 0 1 2-4v-2a6 6 0 0 1-2-4L7 3Z" />
    </svg>
  )
}

export function RefreshIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" />
      <path d="M21 4v4h-4" />
      <path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" />
      <path d="M3 20v-4h4" />
    </svg>
  )
}

export function TrashIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M4 7h16" />
      <path d="M9 7V4h6v3" />
      <path d="M6 7v13a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7" />
    </svg>
  )
}

export function KeyIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="8" cy="15" r="4" />
      <path d="m11 12 9-9M16 7l3 3" />
    </svg>
  )
}

export function LogoutIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4" />
      <path d="M10 17 5 12l5-5" />
      <path d="M5 12h11" />
    </svg>
  )
}

export function XIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M6 6 18 18M18 6 6 18" />
    </svg>
  )
}

export function EmptyDocIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <rect x="4" y="3" width="14" height="18" rx="2" />
      <path d="M8 8h6M8 12h6M8 16h4" />
    </svg>
  )
}

export function AlertIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5M12 16h.01" />
    </svg>
  )
}

export function ExpandIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M14 4v16" />
      <path d="m10 10 2 2-2 2" />
    </svg>
  )
}

export function CollapseIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M14 4v16" />
      <path d="m11 10-2 2 2 2" />
    </svg>
  )
}

export function ListIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
    </svg>
  )
}

export function MenuIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  )
}

export function ScanIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M5 12V8a3 3 0 0 1 3-3h2M19 12V8a3 3 0 0 0-3-3h-2M5 12v4a3 3 0 0 0 3 3h2M19 12v4a3 3 0 0 1-3 3h-2" />
    </svg>
  )
}

export function BranchIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <circle cx="6" cy="6" r="2" />
      <circle cx="6" cy="18" r="2" />
      <circle cx="18" cy="12" r="2" />
      <path d="M6 8v8M8 6h6a4 4 0 0 1 4 4v0" />
    </svg>
  )
}

export function PlusIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

export function MinusIcon(props: IconProps) {
  return (
    <svg {...svgBase(props)}>
      <path d="M5 12h14" />
    </svg>
  )
}
