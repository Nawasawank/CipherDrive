import axios from "axios";
import config from "../config";

const api = axios.create({
    baseURL: config.backendUrl,
});

api.interceptors.request.use((request) => {
    const token = localStorage.getItem("access_token"); 
    if (token) {
        request.headers.Authorization = `Bearer ${token}`;
    }
    return request;
});

export const uploadFile = async (file) => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post("/files/upload", formData);
    return response.data;
};

export const getUserFiles = async () => {
    const response = await api.get("/files/my-files");
    return response.data;
};

export const login = async (email, password) => {
    const response = await api.post("/auth/login", { email, password });
    return response.data;
};

export const register = async (email, password) => {
    const response = await api.post("/auth/register", { email, password });
    return response.data;
};

export const getUserDetails = async () => {
    const response = await api.get("/auth/user-details");
    console.log(response.data);
    return response.data;
};

export const shareFile = async (file_name, shared_with_email, permission) => {
    const res = await api.post("/share/share-file", {
      file_name,
      shared_with_email,
      permission,
    });
    return res.data;
};

export const getSharedFiles = async () => {
    const res = await api.get("/share/shared-files");
    return res.data;
};

export const getFileMetadata = async () => {
    const res = await api.get("/my-files/metadata");
    return res.data;
};

export const previewFile = async (fileName) => {
    const res = await axios.get("/my-files/preview", {file_name: fileName });
    return res.data;
};

export const getAllUsers = async () => {
    const res = await api.get("/admin/users");
    return res.data;
};

export const getUserFilesById = async (userId) => {
    const res = await api.get("/admin/user-files", {
      params: { user_id: userId },
    });
    return res.data;
};

export const deleteFile = async (file_name) => {
    const res = await api.delete("/files/delete-file", {
        params: { file_name },
    });
    return res.data;
};

export const getAdminStats = async () => {
  const res = await api.get("/admin/stats");
  return res.data;
};

export const getActivityLog = async () => {
  const res = await api.get("/admin/activity-log");
  return res.data;
};

export const getSuspiciousActivity = async () => {
  const res = await api.get("/admin/suspicious-activity");
  return res.data;
};

export const getUserActivity = async (email) => {
  const res = await api.get("/admin/user-activity", {
    params: { email },
  });
  return res.data;
};

export const searchUsers = async (query) => {
  const res = await api.get("/admin/search-users", {
    params: { query },
  });
  return res.data;
};

export const filterActivity = async (action_type, date) => {
  const res = await api.get("/admin/filter-activity", {
    params: { action_type, date },
  });
  return res.data;
};

export const lockUser = async (email) => {
  const res = await api.put("/admin/lock-user", null, {
    params: { email },
  });
  return res.data;
};

export const unlockUser = async (email) => {
  const res = await api.put("/admin/unlock-user", null, {
    params: { email },
  });
  return res.data;
};

export default api;