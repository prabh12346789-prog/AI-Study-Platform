import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { NotFoundPage } from '../features/foundation/NotFoundPage'
import { PlaceholderPage } from '../features/foundation/PlaceholderPage'
import { SettingsPage } from '../features/settings/SettingsPage'
import { DashboardPage } from '../features/dashboard/DashboardPage'
import { ChatPage } from '../features/chat/ChatPage'
import { LibraryPage } from '../features/library/LibraryPage'
import { CurrentAffairsPage } from '../features/current-affairs/CurrentAffairsPage'
import { QuizzesPage } from '../features/quizzes/QuizzesPage'
const pages = [
  ['/visual-learning', 'Visual Learning', 'Turn grounded study material into structured visual roadmaps.'],
  ['/revision', 'Revision Center', 'Prioritize due topics using mastery and forgetting-risk evidence.'], ['/progress', 'Progress', 'Understand study consistency, mastery, and actionable trends.'], ['/videos', 'Videos', 'Trusted UPSC video recommendations with transparent reasons.'],
  ['/profile', 'Profile', 'Control your language, depth, format, and learning preferences.'],
] as const
export const appRoutes = [{ path: '/', element: <AppShell />, children: [{ index: true, element: <Navigate to="/dashboard" replace /> }, {path:'dashboard',element:<DashboardPage/>},{path:'coach',element:<ChatPage/>},{path:'library',element:<LibraryPage/>},{path:'current-affairs',element:<CurrentAffairsPage/>},{path:'quizzes',element:<QuizzesPage/>}, ...pages.map(([path, title, description]) => ({ path: path.slice(1), element: <PlaceholderPage title={title} description={description} /> })), { path: 'settings', element: <SettingsPage /> }, { path: '*', element: <NotFoundPage /> }] }]
export const router = createBrowserRouter(appRoutes)
