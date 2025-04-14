import "../styles/ErrorOverlay.css";

export default function ErrorOverlay({ message, onClose }) {
  return (
    <div className="overlay-backdrop">
      <div className="overlay-box">
        <h2 style={{ color: "#d93025" }}>Login Failed</h2>
        <p>{message}</p>
        <button onClick={onClose} className="overlay-button">Try Again</button>
      </div>
    </div>
  );
}
