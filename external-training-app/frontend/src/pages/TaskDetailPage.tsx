import { useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router';
import { ArrowLeft, Clock, Loader2, CheckCircle2, XCircle, XOctagon } from 'lucide-react';
import { useTaskContext, type LogEntry } from '../contexts/TaskContext';

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'pending': return <Clock size={24} className="task-icon pending" />;
    case 'running': return <Loader2 size={24} className="task-icon running spinning" />;
    case 'completed': return <CheckCircle2 size={24} className="task-icon completed" />;
    case 'failed': return <XCircle size={24} className="task-icon failed" />;
    case 'cancelled': return <XOctagon size={24} className="task-icon cancelled" />;
    default: return null;
  }
}

function StatusBadge({ status }: { status: string }) {
  const labels: Record<string, string> = {
    pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', cancelled: '已取消',
  };
  return <span className={`task-badge ${status}`}>{labels[status] || status}</span>;
}

function formatTime(isoString?: string): string {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function LogEntryItem({ entry }: { entry: LogEntry }) {
  if (entry.level === 'token') {
    return <span className="log-token">{entry.message}</span>;
  }

  const levelClass: Record<string, string> = { info: 'info', warning: 'warning', error: 'error' };

  return (
    <div className="log-entry">
      <span className="log-time">{formatTime(entry.timestamp)}</span>
      <span className={`log-level ${levelClass[entry.level] || ''}`}>{entry.level}</span>
      <span className="log-message">{entry.message}</span>
    </div>
  );
}

export function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const { getTask, subscribeToTask } = useTaskContext();
  const logsEndRef = useRef<HTMLDivElement>(null);

  const task = taskId ? getTask(taskId) : undefined;

  useEffect(() => {
    if (!taskId) return;
    const unsubscribe = subscribeToTask(taskId);
    return unsubscribe;
  }, [taskId, subscribeToTask]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [task?.logs.length]);

  if (!task) {
    return (
      <div className="page-container">
        <div className="task-not-found">
          <p>任务不存在或已过期</p>
          <button className="btn btn-secondary" onClick={() => navigate(-1)}>
            <ArrowLeft size={16} /> 返回
          </button>
        </div>
      </div>
    );
  }

  const isRunning = task.status === 'running' || task.status === 'pending';

  const renderLogs = () => {
    const elements: React.ReactNode[] = [];
    let tokenBuffer: string[] = [];

    const flushTokens = () => {
      if (tokenBuffer.length > 0) {
        elements.push(
          <div key={`token-${elements.length}`} className="log-entry token-entry">
            <span className="log-time" />
            <span className="log-level token">token</span>
            <span className="log-token-block">{tokenBuffer.join('')}</span>
          </div>
        );
        tokenBuffer = [];
      }
    };

    for (const entry of task.logs) {
      if (entry.level === 'token') {
        tokenBuffer.push(entry.message);
      } else {
        flushTokens();
        elements.push(<LogEntryItem key={`log-${elements.length}`} entry={entry} />);
      }
    }
    flushTokens();
    return elements;
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <button className="btn btn-secondary" onClick={() => navigate(-1)}>
          <ArrowLeft size={16} /> 返回
        </button>
        <h1>任务详情</h1>
      </div>

      <div className="task-detail-content">
        {/* 状态卡片 */}
        <div className="card task-status-card">
          <div className="task-status-header">
            <StatusIcon status={task.status} />
            <div>
              <h2>{task.title}</h2>
              <p className="task-id">任务 ID: <code>{task.id}</code></p>
            </div>
            <StatusBadge status={task.status} />
          </div>

          <div className="task-time-grid">
            <div>
              <p className="task-time-label">创建时间</p>
              <p className="task-time-value">{formatTime(task.createdAt)}</p>
            </div>
            <div>
              <p className="task-time-label">开始时间</p>
              <p className="task-time-value">{formatTime(task.startedAt)}</p>
            </div>
            <div>
              <p className="task-time-label">完成时间</p>
              <p className="task-time-value">{formatTime(task.completedAt)}</p>
            </div>
          </div>

          {task.error && (
            <div className="task-error">
              <p>{task.error}</p>
            </div>
          )}
        </div>

        {/* 日志区域 */}
        <div className="card task-log-card">
          <div className="task-log-header">
            <h3>执行日志</h3>
            {isRunning && (
              <span className="task-badge running">
                <Loader2 size={14} className="spinning" /> 实时更新中
              </span>
            )}
          </div>
          <div className="task-log-body">
            {task.logs.length === 0 ? (
              <p className="task-log-empty">{isRunning ? '等待日志输出...' : '暂无日志'}</p>
            ) : (
              <div className="task-log-content">
                {renderLogs()}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        </div>

        {/* 结果区域 */}
        {task.status === 'completed' && task.result != null && (
          <div className="card task-result-card">
            <h3>执行结果</h3>
            <pre className="task-result-content">
              {typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
