import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import Landing from '@/pages/Landing';
import SignIn from '@/pages/SignIn';
import Fleet from '@/pages/Fleet';
import VendorDetail from '@/pages/VendorDetail';
import Evidence from '@/pages/Evidence';
import Methodology from '@/pages/Methodology';
import RegisterPage from '@/pages/Register';
import Compare from '@/pages/Compare';
import Settings from '@/pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/signin" element={<SignIn />} />
      <Route element={<AppShell />}>
        <Route path="/fleet" element={<Fleet />} />
        <Route path="/vendor" element={<Navigate to="/vendor/aldermere" replace />} />
        <Route path="/vendor/:id" element={<VendorDetail />} />
        <Route path="/evidence" element={<Evidence />} />
        <Route path="/methodology" element={<Methodology />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
