import { useEffect, useState } from "react";
import {
  getAllUsers,
  getAdminStats,
  getActivityLog,
  getSuspiciousActivity,
  filterActivity,
  searchUsers,
  lockUser,
  unlockUser,
  getUserActivity
} from "../services/api";
import { 
  BarChart, 
  Bar, 
  LineChart, 
  Line, 
  PieChart, 
  Pie, 
  Cell, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer 
} from "recharts";
import "../styles/AdminPage.css";

export default function AdminPanel() {
  const [view, setView] = useState("dashboard");
  const [stats, setStats] = useState(null);
  const [activityLogs, setActivityLogs] = useState([]);
  const [suspicious, setSuspicious] = useState(null);
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  
  // New state for filters and search
  const [searchQuery, setSearchQuery] = useState("");
  const [actionFilter, setActionFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("");
  const [selectedUser, setSelectedUser] = useState(null);
  const [userActivityData, setUserActivityData] = useState([]);

  const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884d8", "#82ca9d"];

  useEffect(() => {
    const fetchAllData = async () => {
      setIsLoading(true);
      try {
        await Promise.all([
          fetchStats(),
          fetchActivity(),
          fetchSuspicious(),
          fetchUsers()
        ]);
      } catch (err) {
        console.error("Error fetching data:", err);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchAllData();
  }, []);

  const fetchStats = async () => {
    try {
      const res = await getAdminStats();
      setStats(res);
      return res;
    } catch (err) {
      console.error("Failed to load stats", err);
      return null;
    }
  };

  const fetchActivity = async () => {
    try {
      const res = await getActivityLog();
      setActivityLogs(res.logs);
      return res.logs;
    } catch (err) {
      console.error("Failed to load activity log", err);
      return [];
    }
  };

  const fetchSuspicious = async () => {
    try {
      const res = await getSuspiciousActivity();
      setSuspicious(res);
      return res;
    } catch (err) {
      console.error("Failed to load suspicious activity", err);
      return null;
    }
  };

  const fetchUsers = async () => {
    try {
      const res = await getAllUsers();
      setUsers(res.users);
      return res.users;
    } catch (err) {
      console.error("Failed to load users", err);
      return [];
    }
  };

  // New functions to handle API interactions
  const handleSearchUsers = async () => {
    if (!searchQuery.trim()) {
      fetchUsers();
      return;
    }
    
    try {
      const res = await searchUsers(searchQuery);
      setUsers(res.users);
    } catch (err) {
      console.error("Failed to search users", err);
    }
  };

  const handleFilterActivity = async () => {
    try {
      const actionType = actionFilter !== "all" ? actionFilter : null;
      const date = dateFilter || null;
      
      const res = await filterActivity(actionType, date);
      setActivityLogs(res.logs);
    } catch (err) {
      console.error("Failed to filter activity", err);
    }
  };

  const handleLockUser = async (email) => {
    try {
      await lockUser(email);
      await fetchUsers();
      await fetchSuspicious();
      await fetchStats(); // 🧠 Refresh stats after locking too
      alert(`User ${email} has been locked`);
    } catch (err) {
      console.error("Failed to lock user", err);
    }
  };
  

  const handleUnlockUser = async (email) => {
    try {
      await unlockUser(email);
      
      setSuspicious(prev => ({
        ...prev,
        blocked_users: prev.blocked_users.filter(user => user !== email)
      }));
      
      await fetchUsers();
      await fetchSuspicious();
      await fetchStats();
      
      alert(`User ${email} has been unlocked`);
    } catch (err) {
      console.error("Failed to unlock user", err);
    }
  };

  const viewUserActivity = async (email) => {
    try {
      setIsLoading(true);
      const res = await getUserActivity(email);
      setSelectedUser(email);
      setUserActivityData(res.logs);
      setView("userDetail");
    } catch (err) {
      console.error("Failed to get user activity", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    window.location.href = "/";
  };

  // Format data for charts
  const prepareUploadsData = () => {
    if (!stats || !stats.uploads_per_user) return [];
    
    // Only show top 5 users for chart clarity
    return stats.uploads_per_user
      .slice(0, 5) // Take top 5 users
      .map(([email, count]) => ({
        name: email.split('@')[0], // Just show username part for chart
        uploads: count
      }));
  };

  const prepareSharesData = () => {
    if (!stats || !stats.shares_per_user) return [];
    
    // Only show top 5 users for chart clarity
    return stats.shares_per_user
      .slice(0, 5)
      .map(([email, count]) => ({
        name: email.split('@')[0],
        shares: count
      }));
  };

  const preparePieData = () => {
    if (!stats) return [];
    return [
      { name: "Uploads", value: stats.total_uploads },
      { name: "Shares", value: stats.total_shares }
    ];
  };

  // Prepare activity data for timeline chart
  const prepareActivityData = () => {
    if (!activityLogs || activityLogs.length === 0) return [];
    
    // Group activities by day and count them
    const grouped = activityLogs.reduce((acc, log) => {
      // Extract date part only
      const date = log.timestamp.split('T')[0];
      if (!acc[date]) acc[date] = 0;
      acc[date]++;
      return acc;
    }, {});
    
    // Convert to array for chart
    return Object.entries(grouped)
      .map(([date, count]) => ({
        date,
        activities: count
      }))
      .sort((a, b) => new Date(a.date) - new Date(b.date))
      .slice(-7); // Last 7 days
  };

  return (
    <div className="admin-panel-dashboard">
      <aside className="admin-panel-sidebar">
        <h1 className="admin-panel-logo">CipherDrive</h1>
        <nav className="admin-panel-nav">
          <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}>📊 Dashboard</button>
          <button className={view === "users" ? "active" : ""} onClick={() => setView("users")}>👥 Users</button>
          <button className={view === "logs" ? "active" : ""} onClick={() => setView("logs")}>📋 Activity Log</button>
          <button className={view === "suspicious" ? "active" : ""} onClick={() => setView("suspicious")}>🚨 Suspicious</button>
          {view === "userDetail" && (
            <button className="active">👤 User Detail</button>
          )}
        </nav>
        <button className="admin-panel-logout-button" onClick={handleLogout}>Logout</button>
      </aside>

      <main className="admin-panel-content">
        {isLoading ? (
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p>Loading dashboard data...</p>
          </div>
        ) : (
          <>
            {view === "dashboard" && stats && (
              <div>
                <h2>📊 Dashboard Overview</h2>
                
                <div className="stats-summary-cards">
                  <div className="stat-card">
                    <h4>Total Users</h4>
                    <p>{users.length}</p>
                  </div>
                  <div className="stat-card">
                    <h4>Total Uploads</h4>
                    <p>{stats.total_uploads}</p>
                  </div>
                  <div className="stat-card">
                    <h4>Total Shares</h4>
                    <p>{stats.total_shares}</p>
                  </div>
                  <div className="stat-card">
                    <h4>Active Today</h4>
                    <p>{activityLogs.filter(log => {
                      const today = new Date().toISOString().split('T')[0];
                      return log.timestamp.includes(today);
                    }).length}</p>
                  </div>
                </div>

                <div className="charts-container">
                  <div className="chart-wrapper">
                    <h3>File Activity Distribution</h3>
                    <ResponsiveContainer width="100%" height={250}>
                      <PieChart>
                        <Pie
                          data={preparePieData()}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="value"
                          label={({name, percent}) => `${name}: ${(percent * 100).toFixed(0)}%`}
                        >
                          {preparePieData().map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                        <Legend />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  
                  <div className="chart-wrapper">
                    <h3>Top User Uploads</h3>
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={prepareUploadsData()}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="uploads" fill="#0088FE" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  
                  <div className="chart-wrapper">
                    <h3>Top User Shares</h3>
                    <ResponsiveContainer width="100%" height={250}>
                      <BarChart data={prepareSharesData()}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="shares" fill="#00C49F" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  
                  <div className="chart-wrapper">
                    <h3>Activity Timeline (Last 7 Days)</h3>
                    <ResponsiveContainer width="100%" height={250}>
                      <LineChart data={prepareActivityData()}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis />
                        <Tooltip />
                        <Line type="monotone" dataKey="activities" stroke="#8884d8" activeDot={{ r: 8 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {view === "users" && (
              <div>
                <h2>👥 User Management</h2>
                <div className="search-filter-container">
                  <input 
                    type="text" 
                    className="search-input" 
                    placeholder="Search users..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearchUsers()}
                  />
                  <button 
                    className="search-button"
                    onClick={handleSearchUsers}
                  >
                    Search
                  </button>
                  <button 
                    className="reset-button"
                    onClick={() => {
                      setSearchQuery('');
                      fetchUsers();
                    }}
                  >
                    Reset
                  </button>
                </div>
                
                <div className="users-table-container">
                  <table className="users-table">
                    <thead>
                      <tr>
                        <th>Email</th>
                        <th>Uploads</th>
                        <th>Shares</th>
                        <th>Last Active</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((user, index) => {
                        const uploadCount = stats?.uploads_per_user.find(([email]) => email === user.email)?.[1] || 0;
                        const shareCount = stats?.shares_per_user.find(([email]) => email === user.email)?.[1] || 0;
                        
                        const userActivities = activityLogs.filter(log => log.email === user.email);
                        const lastActive = userActivities.length > 0 
                          ? new Date(userActivities[0].timestamp).toLocaleDateString()
                          : 'Never';
                        
                        return (
                          <tr key={user.id || index}>
                            <td>{user.email}</td>
                            <td>{uploadCount}</td>
                            <td>{shareCount}</td>
                            <td>{lastActive}</td>
                            <td>
                              <button 
                                className="action-button view-button"
                                onClick={() => viewUserActivity(user.email)}
                              >
                                View
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {view === "logs" && (
              <div>
                <h2>📋 Activity Log</h2>
                <div className="log-filters">
                  <select 
                    className="log-filter"
                    value={actionFilter}
                    onChange={(e) => setActionFilter(e.target.value)}
                  >
                    <option value="all">All Activities</option>
                    <option value="upload">Uploads</option>
                    <option value="share">Shares</option>
                    <option value="delete">Deletions</option>
                    <option value="login">Logins</option>
                    <option value="failed_login">Failed Logins</option>
                  </select>
                  <input 
                    type="date" 
                    className="date-filter" 
                    value={dateFilter}
                    onChange={(e) => setDateFilter(e.target.value)}
                  />
                  <button 
                    className="filter-button"
                    onClick={handleFilterActivity}
                  >
                    Apply Filters
                  </button>
                  <button 
                    className="reset-button"
                    onClick={() => {
                      setActionFilter('all');
                      setDateFilter('');
                      fetchActivity();
                    }}
                  >
                    Reset
                  </button>
                </div>
                
                <div className="activity-logs-container">
                  <table className="activity-table">
                    <thead>
                      <tr>
                        <th>User</th>
                        <th>Action</th>
                        <th>Details</th>
                        <th>Timestamp</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activityLogs.map((log, idx) => (
                        <tr key={idx} className={`activity-${log.action.toLowerCase()}`}>
                          <td>{log.email}</td>
                          <td>{log.action}</td>
                          <td>{log.metadata}</td>
                          <td>{new Date(log.timestamp).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {view === "suspicious" && suspicious && (
              <div>
                <h2>🚨 Security Alerts</h2>
                
                <div className="alert-summary-cards">
                  <div className="alert-card critical">
                    <h4>Blocked Users</h4>
                    <p>{suspicious.blocked_users.length || 0}</p>
                  </div>
                  <div className="alert-card warning">
                    <h4>Suspicious Activities</h4>
                    <p>{suspicious.suspicious_summary.length || 0}</p>
                  </div>
                  <div className="alert-card info">
                    <h4>Last Incident</h4>
                    <p>
                      {suspicious.suspicious_summary.length > 0 
                        ? new Date(suspicious.suspicious_summary[0].last_seen).toLocaleDateString() 
                        : 'None'}
                    </p>
                  </div>
                </div>
                
                {suspicious.blocked_users.length > 0 && (
                  <div className="blocked-users-section">
                    <h3>Blocked Users</h3>
                    <div className="blocked-users-list">
                      {suspicious.blocked_users.map((user, idx) => (
                        <div key={idx} className="blocked-user-card">
                          <span className="user-email">{user}</span>
                          <button 
                            className="unblock-button"
                            onClick={() => handleUnlockUser(user)}
                          >
                            Unblock
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                <div className="suspicious-activity-section">
                  <h3>Suspicious Activity Log</h3>
                  {suspicious.suspicious_summary.length > 0 ? (
                    <table className="suspicious-table">
                      <thead>
                        <tr>
                          <th>User</th>
                          <th>Action</th>
                          <th>Count</th>
                          <th>First Seen</th>
                          <th>Last Seen</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {suspicious.suspicious_summary.map((entry, idx) => (
                          <tr key={idx} className="suspicious-entry">
                            <td>{entry.email}</td>
                            <td>{entry.action}</td>
                            <td>{entry.count}</td>
                            <td>{new Date(entry.first_seen).toLocaleString()}</td>
                            <td>{new Date(entry.last_seen).toLocaleString()}</td>
                            <td>
                              <button 
                                className="action-button block-button"
                                onClick={() => handleLockUser(entry.email)}
                              >
                                Block
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="no-data-message">
                      <p>No suspicious activities detected</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {view === "userDetail" && selectedUser && (
              <div>
                <h2>👤 User Activity: {selectedUser}</h2>
                <button 
                  className="back-button" 
                  onClick={() => setView("users")}
                >
                  ← Back to Users
                </button>
                
                <div className="user-activity-container">
                  <h3>Activity History</h3>
                  {userActivityData.length > 0 ? (
                    <table className="activity-table">
                      <thead>
                        <tr>
                          <th>Action</th>
                          <th>Details</th>
                          <th>Timestamp</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userActivityData.map((log, idx) => (
                          <tr key={idx} className={`activity-${log.action.toLowerCase()}`}>
                            <td>{log.action}</td>
                            <td>{log.metadata}</td>
                            <td>{new Date(log.timestamp).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="no-data-message">
                      <p>No activity found for this user</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}