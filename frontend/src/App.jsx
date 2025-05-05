import { useEffect, useState } from 'react';
import Keycloak from 'keycloak-js';

function App() {
  const [keycloak, setKeycloak] = useState(null);
  const [token, setToken] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);

  // Инициализация Keycloak при монтировании приложения
  useEffect(() => {
    const kc = new Keycloak({
      url: 'http://localhost:8080',    // URL Keycloak-сервера
      realm: 'nica',                   // Realm в Keycloak
      clientId: 'tier1-frontend'       // ID клиента (должен соответствовать настроенному в Keycloak)
    });
    kc.init({ onLoad: 'login-required' }).then((authenticated) => {
      if (authenticated) {
        setKeycloak(kc);
        setToken(kc.token);
      } else {
        console.warn("Not authenticated");
      }
    }).catch(e => {
      console.error("Keycloak init error", e);
    });
  }, []);

  // Получение данных задач и событий после получения токена
  useEffect(() => {
    if (token) {
      const headers = { 'Authorization': 'Bearer ' + token };
      // Запрос списка задач
      fetch('http://localhost:8000/tasks', { headers })
        .then(res => res.json())
        .then(data => setTasks(data))
        .catch(err => console.error("Failed to fetch tasks", err));
      // Запрос списка событий
      fetch('http://localhost:8000/events', { headers })
        .then(res => res.json())
        .then(data => setEvents(data))
        .catch(err => console.error("Failed to fetch events", err));
    }
  }, [token]);

  // Обработчик скачивания файла задачи
  const handleDownload = async (taskId) => {
    if (!token) return;
    try {
      const res = await fetch(`http://localhost:8000/data/${taskId}`, {
        headers: { 'Authorization': 'Bearer ' + token }
      });
      const data = await res.json();
      if (data.url) {
        window.open(data.url, '_blank');  // открываем ссылку на скачивание в новой вкладке
      }
    } catch (err) {
      console.error("Download failed", err);
    }
  };

  if (!keycloak) {
    // Ещё не инициализировано подключение к Keycloak
    return <div>Initializing...</div>;
  }
  if (!keycloak.authenticated) {
    // Теоретически это состояние не должно длиться долго, так как onLoad=login-required перенаправит на вход
    return <div>Redirecting to login...</div>;
  }

  return (
    <div className="app-container" style={{ padding: '1rem' }}>
      <h1>Список задач</h1>
      {tasks.length === 0 ? (
        <p>Нет задач.</p>
      ) : (
        <table className="tasks-table" border="1" cellPadding="8">
          <thead>
            <tr><th>ID</th><th>Название</th><th>Файл</th><th>Размер (байт)</th><th>Дата</th><th></th></tr>
          </thead>
          <tbody>
            {tasks.map(task => (
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
      {events.length === 0 ? (
        <p>Нет событий.</p>
      ) : (
        <ul>
          {events.map((ev, idx) => (
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

