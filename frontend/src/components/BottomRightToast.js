import "../styles/BottomRightToast.css";

export default function BottomRightToast({ message, onClose }) {
  return (
    <div className="bottom-toast">
      <div className="toast-box">
        <span>{message}</span>
        <button onClick={onClose}>✖</button>
      </div>
    </div>
  );
}
