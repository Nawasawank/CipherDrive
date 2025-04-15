import { useState, useEffect } from "react";
import { login } from "../services/api";
import { useNavigate } from "react-router-dom";
import "../styles/Login.css";
import ErrorOverlay from "../components/ErrorOverlay.js";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [showError, setShowError] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      const emailInput = document.getElementById("email");
      const passwordInput = document.getElementById("password");
      if (emailInput?.value) setEmail(emailInput.value);
      if (passwordInput?.value) setPassword(passwordInput.value);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMessage("");
    try {
      const res = await login(email, password);
      localStorage.setItem("access_token", res.access_token);
      localStorage.setItem("userRole", res.role); 
      navigate("/drive");
    } catch (err) {
      setErrorMessage(err.response?.data?.detail || "Login failed");
      setShowError(true);
    } finally {
      setLoading(false);
    }
  };

  const handleOverlayClose = () => {
    setShowError(false);
  };

  return (
    <div className="auth-container">
      <div className="auth-form-container">
        <div className="auth-logo">
          <div className="logo-text">SecureDrive</div>
        </div>
        <h1 className="auth-title">Sign in</h1>
        <p className="auth-subtitle">to continue to SecureDrive</p>

        <form className="auth-form" onSubmit={handleLogin}>
          <div className="form-group">
            <input
              type="email"
              id="email"
              className="auth-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder=" "
              autoComplete="username"
            />
            <label htmlFor="email" className="auth-label">Email</label>
          </div>

          <div className="form-group">
            <input
              type="password"
              id="password"
              className="auth-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder=" "
              autoComplete="current-password"
            />
            <label htmlFor="password" className="auth-label">Password</label>
          </div>

          <div className="auth-actions">
            <a href="/register" className="auth-link">Create account</a>
            <button type="submit" className="auth-button" disabled={loading}>
              {loading ? <span className="loading-spinner"></span> : "Sign in"}
            </button>
          </div>
        </form>
      </div>

      {showError && (
        <ErrorOverlay message={errorMessage} onClose={handleOverlayClose} />
      )}
    </div>
  );
}
