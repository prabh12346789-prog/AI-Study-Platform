import { BookOpen, BrainCircuit, ChartNoAxesCombined, CircleUserRound, ClipboardCheck, Compass, FileStack, LayoutDashboard, Newspaper, RotateCcw, Settings, Video } from 'lucide-react'
export const navigation = [
  ['Dashboard', '/dashboard', LayoutDashboard], ['AI Study Coach', '/coach', BrainCircuit], ['My Library', '/library', FileStack],
  ['Current Affairs', '/current-affairs', Newspaper], ['Quizzes', '/quizzes', ClipboardCheck], ['Visual Learning', '/visual-learning', Compass],
  ['Revision Center', '/revision', RotateCcw], ['Progress', '/progress', ChartNoAxesCombined], ['Videos', '/videos', Video],
  ['Profile', '/profile', CircleUserRound], ['Settings', '/settings', Settings],
] as const
export const productIcon = BookOpen
