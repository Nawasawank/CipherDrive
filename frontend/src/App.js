import React, { useState } from "react";
import Login from "./pages/Login.jsx";
import FileUpload from "./pages/FileUpload.jsx";
import FileList from "./pages/FileList.jsx";

function App() {
    const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem("access_token"));

    const handleLogin = () => {
        setIsLoggedIn(true);
    };

    return (
        <div>
            {!isLoggedIn ? (
                <Login onLogin={handleLogin} />
            ) : (
                <>
                    <FileUpload />
                    <FileList />
                </>
            )}
        </div>
    );
}

export default App;