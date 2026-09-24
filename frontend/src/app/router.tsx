import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/stores/auth'
import AdminPage from '@/pages/AdminPage'
import LoginPage from '@/pages/LoginPage'
import TvDashboardPage from '@/pages/TvDashboardPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated())
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function Router() {
  return (
    <Routes>
      <Route path="/" element={<TvDashboardPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <AdminPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
