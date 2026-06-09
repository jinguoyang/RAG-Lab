import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'token';
  message: string;
  data?: Record<string, unknown>;
}

export interface Task {
  id: string;
  type: string;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  logs: LogEntry[];
  result?: unknown;
  error?: string;
}

export interface TaskSummary {
  id: string;
  type: string;
  title: string;
  status: Task['status'];
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
}

interface TaskContextValue {
  tasks: Map<string, Task>;
  activeTasks: TaskSummary[];
  addTask: (task: Task) => void;
  removeTask: (taskId: string) => void;
  getTask: (taskId: string) => Task | undefined;
  subscribeToTask: (taskId: string) => () => void;
}

const TaskContext = createContext<TaskContextValue | null>(null);

const API_BASE = '/api/v1';

export function TaskProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<Map<string, Task>>(new Map());
  const eventSourcesRef = useRef<Map<string, EventSource>>(new Map());

  const fetchTasks = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/tasks`);
      if (!response.ok) return;
      const data = await response.json();
      setTasks(prev => {
        const next = new Map(prev);
        for (const summary of data.tasks) {
          const existing = next.get(summary.id);
          if (!existing) {
            next.set(summary.id, { ...summary, logs: [] });
          } else {
            next.set(summary.id, {
              ...existing,
              status: summary.status,
              startedAt: summary.startedAt,
              completedAt: summary.completedAt,
              error: summary.error,
            });
          }
        }
        return next;
      });
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    void fetchTasks();
  }, [fetchTasks]);

  const addTask = useCallback((task: Task) => {
    setTasks(prev => {
      const next = new Map(prev);
      next.set(task.id, task);
      return next;
    });
  }, []);

  const removeTask = useCallback((taskId: string) => {
    const es = eventSourcesRef.current.get(taskId);
    if (es) {
      es.close();
      eventSourcesRef.current.delete(taskId);
    }
    setTasks(prev => {
      const next = new Map(prev);
      next.delete(taskId);
      return next;
    });
    void fetch(`${API_BASE}/tasks/${taskId}`, { method: 'DELETE' }).catch(() => {});
  }, []);

  const getTask = useCallback((taskId: string) => {
    return tasks.get(taskId);
  }, [tasks]);

  const subscribeToTask = useCallback((taskId: string) => {
    const existing = eventSourcesRef.current.get(taskId);
    if (existing) existing.close();

    const es = new EventSource(`${API_BASE}/tasks/${taskId}/stream`);
    eventSourcesRef.current.set(taskId, es);

    const handleEvent = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.task) {
          setTasks(prev => {
            const next = new Map(prev);
            const existing = next.get(taskId);
            next.set(taskId, { ...existing, ...data.task, logs: existing?.logs || [] });
            return next;
          });
        }
      } catch { /* ignore */ }
    };

    const handleLog = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.log) {
          setTasks(prev => {
            const next = new Map(prev);
            const existing = next.get(taskId);
            if (existing) {
              next.set(taskId, { ...existing, logs: [...existing.logs, data.log] });
            }
            return next;
          });
        }
      } catch { /* ignore */ }
    };

    const handleToken = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.token) {
          setTasks(prev => {
            const next = new Map(prev);
            const existing = next.get(taskId);
            if (existing) {
              const logEntry: LogEntry = { timestamp: new Date().toISOString(), level: 'token', message: data.token };
              next.set(taskId, { ...existing, logs: [...existing.logs, logEntry] });
            }
            return next;
          });
        }
      } catch { /* ignore */ }
    };

    es.addEventListener('snapshot', handleEvent);
    es.addEventListener('created', handleEvent);
    es.addEventListener('started', handleEvent);
    es.addEventListener('completed', handleEvent);
    es.addEventListener('failed', handleEvent);
    es.addEventListener('cancelled', handleEvent);
    es.addEventListener('log', handleLog);
    es.addEventListener('token', handleToken);
    es.addEventListener('heartbeat', () => {});

    es.onerror = () => {
      es.close();
      eventSourcesRef.current.delete(taskId);
    };

    return () => {
      es.close();
      eventSourcesRef.current.delete(taskId);
    };
  }, []);

  const activeTasks: TaskSummary[] = Array.from(tasks.values())
    .filter(t => t.status === 'pending' || t.status === 'running')
    .map(t => ({
      id: t.id, type: t.type, title: t.title, status: t.status,
      createdAt: t.createdAt, startedAt: t.startedAt, completedAt: t.completedAt, error: t.error,
    }));

  return (
    <TaskContext.Provider value={{ tasks, activeTasks, addTask, removeTask, getTask, subscribeToTask }}>
      {children}
    </TaskContext.Provider>
  );
}

export function useTaskContext() {
  const context = useContext(TaskContext);
  if (!context) throw new Error('useTaskContext must be used within a TaskProvider');
  return context;
}
