import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import MainPage from "./pages/MainPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import { ProtectedRoute } from "./utils/ProtectedRoute.js";

export default function App() {
  return (
    <Router>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<Login />} />
        <Route path="/register" element={<Register />} />
        
        {/* Protected routes for regular users */}
        <Route element={<ProtectedRoute allowedRoles={["user"]} />}>
          <Route path="/drive" element={<MainPage />} />
        </Route>
        
        {/* Protected routes for admins only */}
        <Route element={<ProtectedRoute allowedRoles={["admin"]} />}>
          <Route path="/admin" element={<AdminPage />} />
        </Route>
        
        <Route path="*" element={<ProtectedRoute allowedRoles={[]} />} />

      </Routes>
    </Router>
  );
}