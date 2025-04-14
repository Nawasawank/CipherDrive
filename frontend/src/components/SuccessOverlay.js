import "../styles/SuccessOverlay.css";

export default function SuccessOverlay({ message, onClose }) {
  return (
    <div className="overlay-backdrop">
      <div className="overlay-box">
        <h2>Success</h2>
        <p>{message}</p>
        <button onClick={onClose} className="overlay-button">Continue</button>
      </div>
    </div>
  );
}
