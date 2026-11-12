import { Navigate, Route, Routes } from 'react-router-dom'
import { useApp } from './context/AppContext.jsx'
import Language from './pages/Language.jsx'
import History from './pages/History.jsx'
import ExerciseChoice from './pages/ExerciseChoice.jsx'
import Setup from './pages/Setup.jsx'
import Calibration from './pages/Calibration.jsx'
import Session from './pages/Session.jsx'
import Summary from './pages/Summary.jsx'
import FitScreen from './components/FitScreen.jsx'

// Simple guard: later screens need earlier choices
function Need({ when, to, children }) {
  return when ? children : <Navigate to={to} replace />
}

export default function App() {
  const { patient, exercise, side, baseline, result } = useApp()
  return (
    <FitScreen>
    <Routes>
      <Route path="/" element={<Language />} />
      <Route path="/history" element={<History />} />
      <Route path="/exercise" element={<Need when={patient} to="/history"><ExerciseChoice /></Need>} />
      <Route path="/setup" element={<Need when={exercise} to="/exercise"><Setup /></Need>} />
      <Route path="/calibration" element={<Need when={exercise && side} to="/setup"><Calibration /></Need>} />
      <Route path="/session" element={<Need when={baseline} to="/calibration"><Session /></Need>} />
      <Route path="/summary" element={<Need when={result} to="/exercise"><Summary /></Need>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </FitScreen>
  )
}
