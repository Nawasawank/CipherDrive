import { useState, useEffect } from "react";
import { register } from "../services/api";
import { useNavigate } from "react-router-dom";
import "../styles/Register.css";
import SuccessOverlay from "../components/SuccessOverlay";
import ErrorOverlay from "../components/ErrorOverlay";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [overlayError, setOverlayError] = useState("");
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

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setOverlayError("");

    if (password !== confirmPassword) {
      setOverlayError("Passwords do not match");
      setLoading(false);
      return;
    }

    try {
      await register(email, password);
      setShowSuccess(true);
    } catch (err) {
      setOverlayError(err.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const handleOverlayClose = () => {
    setOverlayError("");        // for error overlay
    setShowSuccess(false);      // for success overlay
    navigate("/");              // go back to home or login
  };

  return (
    <div className="auth-container">
      <div className="auth-form-container">
        <div className="auth-logo">
          <div className="logo-text">CipherDrive</div>
        </div>
        <h1 className="auth-title">Create your account</h1>
        <p className="auth-subtitle">to get started with CipherDrive</p>

        <form className="auth-form" onSubmit={handleRegister}>
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
              autoComplete="new-password"
            />
            <label htmlFor="password" className="auth-label">Password</label>
          </div>

          <div className="form-group">
            <input
              type="password"
              id="confirmPassword"
              className="auth-input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              placeholder=" "
              autoComplete="new-password"
            />
            <label htmlFor="confirmPassword" className="auth-label">Confirm Password</label>
          </div>

          <div className="auth-actions">
            <a href="/" className="auth-link">Already have an account?</a>
            <button type="submit" className="auth-button1" disabled={loading}>
              {loading ? (
                <span className="loading-spinner"></span>
              ) : (
                "Sign up"
              )}
            </button>
          </div>
        </form>
      </div>

      {overlayError && (
        <ErrorOverlay
          message={overlayError}
          onClose={() => setOverlayError("")}
        />
      )}

      {showSuccess && (
        <SuccessOverlay
          message="Your account has been created successfully!"
          onClose={handleOverlayClose}
        />
      )}
    </div>
  );
}
