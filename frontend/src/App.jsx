import { useEffect, useState } from 'react';
import Keycloak from 'keycloak-js';

function App() {
  const [keycloak, setKeycloak] = useState(null);
  const [token, setToken] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    const kc = new Keycloak({
      url: 'http://localhost:8080',
      realm: 'nica',
      clientId: 'tier1-frontend',
    });

    kc.init({ onLoad: 'login-required', scope: 'openid' }).then((authenticated) => {
      if (authenticated) {
        setKeycloak(kc);
        setToken(kc.token);
        console.log("TOKEN:", kc.token);
        setInterval(() => {
          kc.updateToken(30).then(refreshed => {
            if (refreshed) {
              setToken(kc.token);
            }
          }).catch(() => {
            console.warn("Failed to refresh token");
          });
        }, 10000);
      } else {
        console.warn("Not authenticated");
      }
    }).catch(e => {
      console.error("Keycloak init error", e);
    });
  }, []);

  useEffect(() => {
    if (token) {
      const headers = { 'Authorization': 'Bearer ' + token };

      fetch('http://localhost:8000/tasks', { headers })
        .then(res => {
          if (!res.ok) throw new Error("Tasks fetch failed: " + res.status);
          return res.json();
        })
        .then(data => setTasks(data || []))
        .catch(err => console.error("Failed to fetch tasks", err));

      fetch('http://localhost:8000/events', { headers })
        .then(res => {
          if (!res.ok) throw new Error("Events fetch failed: " + res.status);
          return res.json();
        })
        .then(data => setEvents(data || []))
        .catch(err => console.error("Failed to fetch events", err));
    }
  }, [token]);

  const handleDownload = async (taskId) => {
    if (!token) return;
    try {
      const res = await fetch(`http://localhost:8000/data/${taskId}`, {
        headers: { 'Authorization': 'Bearer ' + token }
      });
      if (!res.ok) throw new Error("Download failed: " + res.status);

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = "example.txt";  // имя можно также взять из task.filename при желании
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download failed", err);
    }
  };

  if (!keycloak) return <div>Инициализация Keycloak...</div>;
  if (!keycloak.authenticated) return <div>Перенаправление на вход...</div>;

  return (
    <div className="app-container" style={{ padding: '1rem' }}>
      <h1>Список задач</h1>
      {Array.isArray(tasks) && tasks.length === 0 ? (
        <p>Нет задач.</p>
      ) : (
        <table className="tasks-table" border="1" cellPadding="8">
          <thead>
            <tr><th>ID</th><th>Название</th><th>Файл</th><th>Размер (байт)</th><th>Дата</th><th></th></tr>
          </thead>
          <tbody>
            {tasks?.map(task => (
              <tr key={task.id}>
                <td>{task.id}</td>
                <td>{task.name}</td>
                <td>{task.filename}</td>
                <td>{task.size}</td>
                <td>{task.timestamp}</td>
                <td><button onClick={() => handleDownload(task.id)}>Скачать</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h2 style={{ marginTop: '2rem' }}>События</h2>
      {Array.isArray(events) && events.length === 0 ? (
        <p>Нет событий.</p>
      ) : (
        <ul>
          {events?.map((ev, idx) => (
            <li key={idx}>
              [{ev.timestamp}] Задача {ev.task_id}: {ev.event}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default App;